from __future__ import annotations

import hashlib
from io import BytesIO
import shutil
from pathlib import Path
from typing import Iterable
from dataclasses import dataclass

try:
    import fitz
except ImportError:  # pragma: no cover - exercised by environment setup
    fitz = None

from PIL import Image, ImageChops, ImageStat

from .binding import build_plan
from .models import AutoFidelityDecision, ExportReport, ExportResult, ImpositionPlan, ImpositionSettings, PdfInspectResult, PdfPageInfo, PageSlot, PaperPreset, PreflightItem, PunchingTemplateInfo, SewingStation


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "backend" / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = ROOT / "outputs"
PREVIEW_DIR = DATA_DIR / "previews"
TOOLS_DIR = DATA_DIR / "tools"
PT_PER_IN = 72
PT_PER_MM = PT_PER_IN / 25.4
TEMPLATE_WIDTH_MM = 45


@dataclass(frozen=True)
class SewingLayout:
    station_count: int
    tape_supports: bool
    tape_count: int


@dataclass
class AutoFidelityState:
    decisions: dict[int, AutoFidelityDecision]
    warnings: list[str]


def ensure_dirs() -> None:
    for path in (UPLOAD_DIR, OUTPUT_DIR, PREVIEW_DIR, TOOLS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def require_fitz():
    if fitz is None:
        raise RuntimeError("PyMuPDF is required. Install dependencies with: python3 -m pip install -r requirements.txt")
    return fitz


def save_upload(filename: str, data: bytes) -> tuple[str, Path]:
    ensure_dirs()
    digest = hashlib.sha256(data).hexdigest()[:16]
    safe_name = "".join(ch for ch in Path(filename).name if ch.isalnum() or ch in " ._-").strip() or "input.pdf"
    job_id = digest
    path = UPLOAD_DIR / f"{job_id}-{safe_name}"
    path.write_bytes(data)
    return job_id, path


def path_for_job(job_id: str) -> Path:
    matches = sorted(UPLOAD_DIR.glob(f"{job_id}-*"))
    if not matches:
        raise FileNotFoundError(f"No PDF upload exists for job {job_id}.")
    return matches[0]


def inspect_pdf(path: Path, job_id: str | None = None) -> PdfInspectResult:
    pdf = require_fitz()
    doc = pdf.open(path)
    warnings: list[str] = []
    preflight: list[PreflightItem] = []
    if doc.needs_pass:
        warnings.append("This PDF is encrypted and needs a password before it can be imposed.")
        preflight.append(_preflight("danger", "Encrypted PDF", "The file requires a password before pages can be read.", "Export an unlocked copy or add password support before imposing this file."))
    if doc.page_count == 0:
        warnings.append("This PDF has no pages.")
        preflight.append(_preflight("danger", "No pages", "The PDF does not contain any pages.", "Choose a different PDF."))

    page_infos: list[PdfPageInfo] = []
    sizes: set[tuple[int, int]] = set()
    rotations: set[int] = set()
    page_box_issues = 0
    annotation_pages = 0
    image_pages = 0
    for index in range(doc.page_count):
        page = doc.load_page(index)
        rect = page.cropbox if page.cropbox and not page.cropbox.is_empty else page.mediabox
        sizes.add((round(rect.width), round(rect.height)))
        rotations.add(page.rotation)
        if not page.cropbox or page.cropbox.is_empty:
            page_box_issues += 1
        if page.first_annot:
            annotation_pages += 1
        if page.get_images(full=True):
            image_pages += 1
        page_infos.append(
            PdfPageInfo(
                index=index + 1,
                width=rect.width,
                height=rect.height,
                rotation=page.rotation,
                boxes={
                    "media": _rect_tuple(page.mediabox),
                    "crop": _rect_tuple(page.cropbox),
                    "trim": _rect_tuple(page.trimbox),
                    "bleed": _rect_tuple(page.bleedbox),
                },
            )
        )

    if len(sizes) > 1:
        warnings.append("This PDF has mixed page sizes; inspect the preview before printing.")
        preflight.append(_preflight("warning", "Mixed page sizes", "Pages do not all share the same dimensions.", "Use full flattening and inspect the rendered preview/contact sheet."))
    else:
        preflight.append(_preflight("ok", "Page sizes", "All sampled pages use the same page size.", "No action needed."))
    if len(rotations) > 1 or (rotations and next(iter(rotations)) != 0):
        preflight.append(_preflight("info", "Page rotation", f"Detected page rotations: {', '.join(str(r) for r in sorted(rotations))}.", "Inspect the preview before printing."))
    if page_box_issues:
        preflight.append(_preflight("warning", "Missing CropBox", f"{page_box_issues} page(s) have no usable CropBox.", "Use MediaBox or flattening if content appears clipped."))
    if annotation_pages:
        preflight.append(_preflight("warning", "Annotations", f"{annotation_pages} page(s) contain annotations.", "Flattening is safest if annotations must print exactly as shown."))
    if image_pages:
        preflight.append(_preflight("info", "Image-heavy PDF", f"{image_pages} page(s) contain embedded images.", "Full flattening is reliable for print output, though files will be larger."))
    if _has_forms(doc):
        preflight.append(_preflight("warning", "Form fields", "This PDF appears to contain AcroForm fields.", "Flatten before printing unless you are certain form appearances are embedded."))
    if _has_layers(doc):
        preflight.append(_preflight("warning", "Optional content/layers", "This PDF appears to contain layers or optional content groups.", "Flattening is recommended for predictable printing."))
    if _has_modern_risk(doc):
        warnings.append("This PDF uses images, masks, or newer PDF features; Auto fidelity validation is recommended.")
        preflight.append(_preflight("warning", "Modern PDF features", "The file uses features that older or simpler PDF processors often mishandle.", "Use Auto / Best Quality, or Raster mode if you need complete flattening."))

    version = getattr(doc, "pdf_version", None)
    if not version:
        version = (doc.metadata or {}).get("format")
    result = PdfInspectResult(
        job_id=job_id or hashlib.sha256(str(path).encode()).hexdigest()[:16],
        filename=path.name,
        path=str(path),
        page_count=doc.page_count,
        pdf_version=str(version) if version else None,
        encrypted=bool(doc.needs_pass),
        pages=page_infos[:20],
        warnings=warnings,
        preflight=preflight,
    )
    doc.close()
    return result


def plan_for_job(settings: ImpositionSettings) -> ImpositionPlan:
    path = path_for_job(settings.job_id)
    info = inspect_pdf(path, settings.job_id)
    plan = build_plan(info.page_count, settings)
    plan.warnings.extend(info.warnings)
    return plan


def export_job(settings: ImpositionSettings) -> ExportResult:
    path = path_for_job(settings.job_id)
    plan = plan_for_job(settings)
    output_root = OUTPUT_DIR / settings.job_id
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    if settings.split_output == "combined":
        out_path = output_root / "bookbinder4-combined.pdf"
        export_report = _write_pdf(path, out_path, settings, plan.sheets)
        outputs = [str(out_path)]
    else:
        outputs = []
        reports = []
        for signature in plan.signatures:
            sheets = [plan.sheets[index] for index in signature.sheets]
            out_path = output_root / f"signature-{signature.index + 1:02d}.pdf"
            reports.append(_write_pdf(path, out_path, settings, sheets))
            outputs.append(str(out_path))
        export_report = _merge_export_reports(settings, reports)

    validation_warnings = validate_export_outputs(outputs)
    validation_warnings.extend(export_report.warnings)

    return ExportResult(
        job_id=settings.job_id,
        output_paths=outputs,
        validation_warnings=validation_warnings,
        plan=plan,
        export_report=export_report,
    )


def create_contact_sheet(settings: ImpositionSettings) -> Path:
    ensure_dirs()
    path = path_for_job(settings.job_id)
    plan = plan_for_job(settings)
    output_path = OUTPUT_DIR / settings.job_id / "preview-contact-sheet.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_pdf = PREVIEW_DIR / f"{settings.job_id}-contact-source.pdf"
    _write_pdf(path, tmp_pdf, settings, plan.sheets)

    pdf = require_fitz()
    source = pdf.open(tmp_pdf)
    contact = pdf.open()
    page_w, page_h = 792, 612
    margin = 30
    label_h = 16
    columns = 2
    rows = 2
    cell_w = (page_w - margin * 2) / columns
    cell_h = (page_h - margin * 2) / rows

    for source_index in range(source.page_count):
        if source_index % 4 == 0:
            contact_page = contact.new_page(width=page_w, height=page_h)
        else:
            contact_page = contact[-1]
        cell_index = source_index % 4
        col = cell_index % columns
        row = cell_index // columns
        x0 = margin + col * cell_w
        y0 = margin + row * cell_h
        rect = pdf.Rect(x0, y0 + label_h, x0 + cell_w - 12, y0 + cell_h - 10)
        contact_page.insert_text((x0, y0 + 10), f"Sheet {source_index // 2 + 1} {'front' if source_index % 2 == 0 else 'back'}", fontsize=9)
        contact_page.show_pdf_page(rect, source, source_index, keep_proportion=True)

    contact.save(output_path, garbage=4, deflate=True)
    contact.close()
    source.close()
    return output_path


def create_calibration_page(paper: PaperPreset, print_safe_margin: float = 14.2, flip_edge: str = "short") -> Path:
    ensure_dirs()
    pdf = require_fitz()
    out_path = TOOLS_DIR / f"calibration-{paper.name.lower().replace(' ', '-')}.pdf"
    sheet_w = max(paper.width, paper.height)
    sheet_h = min(paper.width, paper.height)
    doc = pdf.open()
    page = doc.new_page(width=sheet_w, height=sheet_h)
    center_x = sheet_w / 2
    center_y = sheet_h / 2
    page.insert_text((36, 36), "Bookbinder 4 Printer Calibration", fontsize=18)
    page.insert_text((36, 58), "Print at 100% / Actual Size. Measure the rulers and fold/flip alignment.", fontsize=10)
    page.insert_text((36, 76), f"Expected booklet duplex: flip on {flip_edge} edge.", fontsize=9)
    page.insert_text((36, 94), "FRONT TEST PAGE", fontsize=10, color=(0, 0.2, 0.8))
    page.insert_text((sheet_w - 124, 94), "BACK TEST PAGE", fontsize=10, color=(0.65, 0, 0.65))
    page.draw_line((center_x, 0), (center_x, sheet_h), color=(1, 0, 0), width=0.8)
    page.draw_line((0, center_y), (sheet_w, center_y), color=(0, 0.3, 0.9), width=0.6)
    page.insert_text((center_x + 6, 20), "fold centerline", fontsize=8, color=(1, 0, 0))
    safe = pdf.Rect(print_safe_margin, print_safe_margin, sheet_w - print_safe_margin, sheet_h - print_safe_margin)
    page.draw_rect(safe, color=(0, 0.55, 0.2), width=1)
    page.insert_text((safe.x0 + 6, safe.y0 + 14), f"print-safe area ({print_safe_margin / PT_PER_MM:.1f} mm margin)", fontsize=8, color=(0, 0.45, 0.2))
    square = pdf.Rect(sheet_w - 108, sheet_h - 108, sheet_w - 36, sheet_h - 36)
    page.draw_rect(square, color=(0, 0, 0), width=0.8)
    page.insert_text((square.x0, square.y0 - 8), "1 inch square", fontsize=8)

    for offset in range(0, int(sheet_w // 2), 36):
        for x in (center_x - offset, center_x + offset):
            page.draw_line((x, center_y - 8), (x, center_y + 8), color=(0, 0, 0), width=0.4)
    for offset in range(0, int(sheet_h // 2), 36):
        for y in (center_y - offset, center_y + offset):
            page.draw_line((center_x - 8, y), (center_x + 8, y), color=(0, 0, 0), width=0.4)

    _draw_crop_marks(page, sheet_w, sheet_h)
    _draw_horizontal_ruler(page, 72, sheet_h - 50, 5 * PT_PER_IN, "5 inch ruler", PT_PER_IN, PT_PER_IN / 2)
    _draw_horizontal_ruler(page, 72, sheet_h - 88, 100 * PT_PER_MM, "100 mm ruler", 10 * PT_PER_MM, 5 * PT_PER_MM)
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


def punching_template_info(settings: ImpositionSettings) -> PunchingTemplateInfo:
    folded_height = min(settings.paper.width, settings.paper.height)
    width = TEMPLATE_WIDTH_MM * PT_PER_MM
    stations = _station_positions(folded_height, settings)
    return PunchingTemplateInfo(
        width_pt=width,
        height_pt=folded_height,
        width_mm=width / PT_PER_MM,
        height_mm=folded_height / PT_PER_MM,
        folded_signature_height_pt=folded_height,
        folded_signature_height_mm=folded_height / PT_PER_MM,
        station_positions=[SewingStation(index=index + 1, y_pt=y, y_mm=y / PT_PER_MM) for index, y in enumerate(stations)],
    )


def create_punching_template(settings: ImpositionSettings) -> Path:
    ensure_dirs()
    pdf = require_fitz()
    info = punching_template_info(settings)
    safe_name = (settings.project_name or settings.job_id or "book").lower().replace(" ", "-")
    out_path = TOOLS_DIR / f"punching-template-{safe_name}.pdf"
    doc = pdf.open()
    page = doc.new_page(width=info.width_pt, height=info.height_pt)
    center_x = info.width_pt / 2
    stations = [station.y_pt for station in info.station_positions]
    margin = settings.sewing_station_margin

    page.insert_text((8, 14), "HEAD", fontsize=10)
    page.insert_text((8, info.height_pt - 8), "TAIL", fontsize=10)
    page.insert_text((center_x + 4, 28), "SPINE/FOLD", fontsize=8, color=(1, 0, 0))
    if settings.project_name:
        page.insert_text((8, 30), settings.project_name[:28], fontsize=7)
    layout = _effective_sewing_layout(settings)
    page.insert_text((8, 42), f"{layout.station_count} stations, {margin / PT_PER_MM:.1f} mm head/tail", fontsize=6.5)
    page.insert_text((8, 52), "Print at 100% / Actual Size", fontsize=6.5, color=(0.75, 0, 0))

    page.draw_line((center_x, 0), (center_x, info.height_pt), color=(1, 0, 0), width=0.7)
    page.draw_line((center_x - 10, margin), (center_x + 10, margin), color=(0, 0.45, 0.2), width=0.45)
    page.draw_line((center_x - 10, info.height_pt - margin), (center_x + 10, info.height_pt - margin), color=(0, 0.45, 0.2), width=0.45)
    page.insert_text((center_x + 12, margin + 3), f"{margin / PT_PER_MM:.1f} mm", fontsize=6, color=(0, 0.4, 0.2))

    if layout.tape_supports and layout.tape_count:
        _draw_tape_zones(page, center_x, stations, settings)

    for index, y in enumerate(stations, start=1):
        page.draw_line((center_x - 13, y), (center_x + 13, y), color=(0, 0, 0), width=0.65)
        page.draw_circle((center_x, y), 2.1, color=(0, 0, 0), fill=(1, 1, 1), width=0.5)
        page.insert_text((center_x + 16, y + 2), str(index), fontsize=7)

    _draw_vertical_mm_ruler(page, 7, 0, info.height_pt)
    _draw_vertical_inch_ruler(page, info.width_pt - 9, 0, info.height_pt)
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


def _draw_horizontal_ruler(page, x0: float, y: float, length: float, label: str, major_step: float, minor_step: float) -> None:
    page.draw_line((x0, y), (x0 + length, y), color=(0, 0, 0), width=0.5)
    x = x0
    major_index = 0
    while x <= x0 + length + 0.1:
        major = abs((x - x0) % major_step) < 0.1
        page.draw_line((x, y - (8 if major else 5)), (x, y + (8 if major else 5)), color=(0, 0, 0), width=0.4)
        if major:
            page.insert_text((x - 3, y + 20), str(major_index), fontsize=7)
            major_index += 1
        x += minor_step
    page.insert_text((x0, y + 34), label, fontsize=8)


def _draw_vertical_mm_ruler(page, x: float, y0: float, height: float) -> None:
    y = y0
    mm = 0
    while y <= y0 + height + 0.1:
        major = mm % 10 == 0
        page.draw_line((x, y), (x + (8 if major else 5), y), color=(0, 0, 0), width=0.35)
        if major and mm > 0:
            page.insert_text((x + 10, y + 2), f"{mm} mm", fontsize=5)
        mm += 5
        y += 5 * PT_PER_MM


def _draw_vertical_inch_ruler(page, x: float, y0: float, height: float) -> None:
    y = y0
    eighths = 0
    while y <= y0 + height + 0.1:
        major = eighths % 8 == 0
        page.draw_line((x - (8 if major else 5), y), (x, y), color=(0, 0, 0), width=0.35)
        if major and eighths > 0:
            page.insert_text((x - 30, y + 2), f"{eighths // 8} in", fontsize=5)
        eighths += 1
        y += PT_PER_IN / 8


def _draw_tape_zones(page, center_x: float, stations: list[float], settings: ImpositionSettings) -> None:
    if len(stations) < 2:
        return
    pdf = require_fitz()
    layout = _effective_sewing_layout(settings)
    usable_top = stations[0]
    usable_bottom = stations[-1]
    span = usable_bottom - usable_top
    for index in range(layout.tape_count):
        y = usable_top + span * (index + 1) / (layout.tape_count + 1)
        rect = pdf.Rect(center_x - 15, y - settings.tape_width / 2, center_x + 15, y + settings.tape_width / 2)
        page.draw_rect(rect, color=(0.1, 0.35, 0.75), fill=(0.88, 0.93, 1), width=0.45)
        page.insert_text((center_x + 18, y + 2), f"tape {index + 1}", fontsize=6, color=(0.1, 0.25, 0.65))


def _station_positions(height: float, settings: ImpositionSettings) -> list[float]:
    count = max(2, _effective_sewing_layout(settings).station_count)
    inset = min(settings.sewing_station_margin, max(0, height / 2 - 6))
    usable = max(0, height - inset * 2)
    step = usable / (count - 1) if count > 1 else 0
    return [inset + step * index for index in range(count)]


def _effective_sewing_layout(settings: ImpositionSettings) -> SewingLayout:
    if settings.sewing_layout == "unsupported_3":
        return SewingLayout(station_count=3, tape_supports=False, tape_count=0)
    if settings.sewing_layout == "unsupported_5":
        return SewingLayout(station_count=5, tape_supports=False, tape_count=0)
    if settings.sewing_layout == "two_tape":
        return SewingLayout(station_count=4, tape_supports=True, tape_count=2)
    if settings.sewing_layout == "three_tape":
        return SewingLayout(station_count=5, tape_supports=True, tape_count=3)
    return SewingLayout(
        station_count=settings.sewing_station_count,
        tape_supports=settings.tape_supports,
        tape_count=settings.tape_count,
    )


def render_preview(settings: ImpositionSettings, sheet_index: int, side: str = "front") -> Path:
    path = path_for_job(settings.job_id)
    plan = plan_for_job(settings)
    sheet = plan.sheets[sheet_index]
    preview_path = PREVIEW_DIR / f"{settings.job_id}-sheet-{sheet_index + 1}-{side}.png"
    tmp_pdf = PREVIEW_DIR / f"{settings.job_id}-sheet-{sheet_index + 1}.pdf"
    _write_pdf(path, tmp_pdf, settings, [sheet])

    pdf = require_fitz()
    doc = pdf.open(tmp_pdf)
    page = doc.load_page(0 if side == "front" else min(1, doc.page_count - 1))
    pix = page.get_pixmap(matrix=pdf.Matrix(2.5, 2.5), alpha=False)
    pix.save(preview_path)
    doc.close()
    return preview_path


def _write_pdf(source_path: Path, out_path: Path, settings: ImpositionSettings, sheets: Iterable) -> ExportReport:
    pdf = require_fitz()
    source = pdf.open(source_path)
    target = pdf.open()
    sheet_w = max(settings.paper.width, settings.paper.height)
    sheet_h = min(settings.paper.width, settings.paper.height)
    auto_state = AutoFidelityState(decisions={}, warnings=[])
    report = ExportReport(
        fidelity=settings.fidelity,
        total_slots=0,
        vector_slots=0,
        raster_slots=0,
        manual_raster_pages=sorted(set(settings.manual_raster_pages)),
        manual_vector_pages=sorted(set(settings.manual_vector_pages)),
    )

    manual_conflicts = sorted(set(settings.manual_raster_pages) & set(settings.manual_vector_pages))
    if manual_conflicts:
        report.warnings.append(f"Pages listed in both manual raster and manual vector overrides used vector: {', '.join(str(page) for page in manual_conflicts)}.")

    for sheet in sheets:
        for side_name in ("front", "back"):
            output_page = target.new_page(width=sheet_w, height=sheet_h)
            slots = getattr(sheet, side_name)
            for slot in slots:
                if slot.is_blank:
                    continue
                report.total_slots += 1
                if _slot_uses_raster(source, slot, settings, auto_state):
                    _place_raster(output_page, source, slot, settings)
                    report.raster_slots += 1
                else:
                    _place_vector(output_page, source, slot, settings)
                    report.vector_slots += 1
            if settings.crop_marks:
                _draw_crop_marks(output_page, sheet_w, sheet_h)
            if settings.sewing_debug_marks:
                _draw_debug_sewing_marks(output_page, sheet_w, sheet_h, settings, side_name)
            if settings.sewing_marks:
                _draw_sewing_marks(output_page, sheet_w, sheet_h, settings)

    target.save(out_path, garbage=4, deflate=True)
    target.close()
    source.close()
    report.decisions = sorted(auto_state.decisions.values(), key=lambda decision: decision.source_page)
    report.auto_validated_pages = len([decision for decision in report.decisions if decision.reason.startswith("auto")])
    report.raster_fallback_pages = [decision.source_page for decision in report.decisions if decision.mode == "raster"]
    report.warnings.extend(auto_state.warnings)
    return report


def _slot_uses_raster(source, slot: PageSlot, settings: ImpositionSettings, auto_state: AutoFidelityState) -> bool:
    page_number = slot.source_page
    if page_number is None:
        return False
    if settings.fidelity == "raster":
        return True
    if settings.fidelity == "vector":
        return False
    decision = _auto_fidelity_decision(source, page_number, settings, auto_state)
    return decision.mode == "raster"


def _auto_fidelity_decision(source, page_number: int, settings: ImpositionSettings, auto_state: AutoFidelityState) -> AutoFidelityDecision:
    if page_number in auto_state.decisions:
        return auto_state.decisions[page_number]

    if page_number in settings.manual_vector_pages:
        decision = AutoFidelityDecision(source_page=page_number, mode="vector", reason="manual vector override")
    elif page_number in settings.manual_raster_pages:
        decision = AutoFidelityDecision(source_page=page_number, mode="raster", reason="manual raster override")
    else:
        decision = _validate_source_page_for_auto(source, page_number, settings, auto_state)

    auto_state.decisions[page_number] = decision
    return decision


def _validate_source_page_for_auto(source, page_number: int, settings: ImpositionSettings, auto_state: AutoFidelityState) -> AutoFidelityDecision:
    try:
        reference, vector = _render_auto_comparison_pair(source, page_number, settings)
        diff_score = _compare_images(reference, vector, settings)
        mode = "vector" if diff_score <= settings.auto_diff_threshold else "raster"
        reason = "auto validation passed" if mode == "vector" else "auto validation exceeded threshold"
        return AutoFidelityDecision(
            source_page=page_number,
            mode=mode,
            reason=reason,
            diff_score=round(diff_score, 4),
            threshold=settings.auto_diff_threshold,
        )
    except Exception as exc:
        auto_state.warnings.append(f"Auto fidelity validation failed for source page {page_number}; using raster fallback. {exc}")
        return AutoFidelityDecision(
            source_page=page_number,
            mode="raster",
            reason="auto validation error",
            diff_score=None,
            threshold=settings.auto_diff_threshold,
        )


def _render_auto_comparison_pair(source, page_number: int, settings: ImpositionSettings) -> tuple[Image.Image, Image.Image]:
    pdf = require_fitz()
    src_page = source.load_page(page_number - 1)
    source_rect = _source_rect(src_page, settings.source_box.value)
    scale = settings.auto_validation_dpi / 72
    matrix = pdf.Matrix(scale, scale)

    reference_pix = src_page.get_pixmap(matrix=matrix, clip=source_rect, alpha=False)

    validation_doc = pdf.open()
    validation_page = validation_doc.new_page(width=source_rect.width, height=source_rect.height)
    validation_page.show_pdf_page(validation_page.rect, source, page_number - 1, clip=source_rect, keep_proportion=True)
    vector_pix = validation_page.get_pixmap(matrix=matrix, alpha=False)
    validation_doc.close()

    return _pixmap_to_image(reference_pix), _pixmap_to_image(vector_pix)


def _pixmap_to_image(pixmap) -> Image.Image:
    return Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")


def _compare_images(reference: Image.Image, candidate: Image.Image, settings: ImpositionSettings) -> float:
    if reference.size != candidate.size:
        candidate = candidate.resize(reference.size)
    diff = ImageChops.difference(reference, candidate)
    if settings.auto_diff_mode == "pixel":
        pixels = diff.getdata()
        changed = sum(1 for pixel in pixels if max(pixel) > 12)
        return changed * 100 / max(1, reference.width * reference.height)
    stat = ImageStat.Stat(diff)
    return sum(value**2 for value in stat.rms) ** 0.5


def _merge_export_reports(settings: ImpositionSettings, reports: list[ExportReport]) -> ExportReport:
    decisions: dict[int, AutoFidelityDecision] = {}
    warnings: list[str] = []
    for report in reports:
        warnings.extend(report.warnings)
        for decision in report.decisions:
            existing = decisions.get(decision.source_page)
            if existing is None or (existing.mode == "vector" and decision.mode == "raster"):
                decisions[decision.source_page] = decision

    merged_decisions = sorted(decisions.values(), key=lambda decision: decision.source_page)
    return ExportReport(
        fidelity=settings.fidelity,
        total_slots=sum(report.total_slots for report in reports),
        vector_slots=sum(report.vector_slots for report in reports),
        raster_slots=sum(report.raster_slots for report in reports),
        auto_validated_pages=len([decision for decision in merged_decisions if decision.reason.startswith("auto")]),
        raster_fallback_pages=[decision.source_page for decision in merged_decisions if decision.mode == "raster"],
        manual_raster_pages=sorted(set(settings.manual_raster_pages)),
        manual_vector_pages=sorted(set(settings.manual_vector_pages)),
        decisions=merged_decisions,
        warnings=warnings,
    )


def _place_vector(output_page, source, slot: PageSlot, settings: ImpositionSettings) -> None:
    pdf = require_fitz()
    src_page = source.load_page(slot.source_page - 1)
    source_rect = _source_rect(src_page, settings.source_box.value)
    dest = _fit_rect(pdf.Rect(slot.rect), source_rect, settings)
    output_page.show_pdf_page(dest, source, slot.source_page - 1, clip=source_rect, keep_proportion=settings.fit_mode != "stretch")


def _place_raster(output_page, source, slot: PageSlot, settings: ImpositionSettings) -> None:
    pdf = require_fitz()
    src_page = source.load_page(slot.source_page - 1)
    source_rect = _source_rect(src_page, settings.source_box.value)
    scale = settings.raster_dpi / 72
    pix = src_page.get_pixmap(matrix=pdf.Matrix(scale, scale), clip=source_rect, alpha=False)
    dest = _fit_rect(pdf.Rect(slot.rect), source_rect, settings)
    output_page.insert_image(dest, pixmap=pix, keep_proportion=settings.fit_mode != "stretch")


def _preflight(severity: str, title: str, detail: str, recommendation: str) -> PreflightItem:
    return PreflightItem(severity=severity, title=title, detail=detail, recommendation=recommendation)


def _has_forms(doc) -> bool:
    try:
        value = getattr(doc, "is_form_pdf", False)
        return bool(value() if callable(value) else value)
    except Exception:
        try:
            return bool(doc.need_appearances())
        except Exception:
            return False


def _has_layers(doc) -> bool:
    try:
        return bool(doc.get_ocgs())
    except Exception:
        return False


def _source_rect(page, box_name: str):
    mapping = {
        "media": page.mediabox,
        "trim": page.trimbox,
        "bleed": page.bleedbox,
        "crop": page.cropbox,
    }
    rect = mapping.get(box_name) or page.cropbox or page.mediabox
    return rect if rect and not rect.is_empty else page.mediabox


def _fit_rect(dest, source_rect, settings: ImpositionSettings):
    pdf = require_fitz()
    if settings.fit_mode == "stretch":
        return dest
    source_ratio = source_rect.width / source_rect.height
    dest_ratio = dest.width / dest.height
    use_width = dest_ratio < source_ratio if settings.fit_mode == "fit" else dest_ratio > source_ratio
    if use_width:
        width = dest.width
        height = width / source_ratio
    else:
        height = dest.height
        width = height * source_ratio
    x0 = dest.x0 + (dest.width - width) / 2
    y0 = dest.y0 + (dest.height - height) / 2
    return pdf.Rect(x0, y0, x0 + width, y0 + height)


def _draw_crop_marks(page, width: float, height: float) -> None:
    mark = 18
    for x, y, dx, dy in (
        (0, 0, mark, 0),
        (0, 0, 0, mark),
        (width, 0, -mark, 0),
        (width, 0, 0, mark),
        (0, height, mark, 0),
        (0, height, 0, -mark),
        (width, height, -mark, 0),
        (width, height, 0, -mark),
    ):
        page.draw_line((x, y), (x + dx, y + dy), color=(0, 0, 0), width=0.5)


def _draw_sewing_marks(page, width: float, height: float, settings: ImpositionSettings) -> None:
    center_x = width / 2
    half_mark = settings.sewing_mark_length / 2
    for y in _station_positions(height, settings):
        page.draw_line((center_x - half_mark, y), (center_x + half_mark, y), color=(0, 0, 0), width=0.45)
        page.draw_circle((center_x, y), 1.2, color=(0, 0, 0), fill=(1, 1, 1), width=0.35)


def _draw_debug_sewing_marks(page, width: float, height: float, settings: ImpositionSettings, side_name: str) -> None:
    center_x = width / 2
    stations = _station_positions(height, settings)
    page.draw_line((center_x, 0), (center_x, height), color=(1, 0, 0), width=0.55)
    page.insert_text((center_x + 5, 16), "SPINE/FOLD", fontsize=7, color=(1, 0, 0))
    page.insert_text((18, 16), "HEAD", fontsize=8)
    page.insert_text((18, height - 10), "TAIL", fontsize=8)
    page.insert_text((width - 112, 16), "FORE EDGE", fontsize=8)
    page.insert_text((18, 32), f"{side_name.upper()} - duplex flip on {settings.flip_edge} edge", fontsize=7, color=(0.1, 0.2, 0.55))
    layout = _effective_sewing_layout(settings)
    if layout.tape_supports and layout.tape_count:
        _draw_tape_zones(page, center_x, stations, settings)
    for index, y in enumerate(stations, start=1):
        page.draw_line((center_x - 18, y), (center_x + 18, y), color=(0, 0, 0), width=0.45)
        page.draw_circle((center_x, y), 1.6, color=(0, 0, 0), fill=(1, 1, 1), width=0.35)
        page.insert_text((center_x + 20, y + 2), f"{index}", fontsize=7)
    _draw_vertical_mm_ruler(page, 12, 0, height)
    _draw_vertical_inch_ruler(page, width - 12, 0, height)


def validate_export_outputs(paths: list[str]) -> list[str]:
    warnings: list[str] = []
    pdf = require_fitz()
    for path in paths:
        doc = pdf.open(path)
        if doc.page_count == 0:
            warnings.append(f"{Path(path).name} has no pages.")
        doc.close()
    return warnings


def _has_modern_risk(doc) -> bool:
    if str(getattr(doc, "pdf_version", "")) >= "1.5":
        return True
    sample = min(doc.page_count, 10)
    for index in range(sample):
        if doc.load_page(index).get_images(full=True):
            return True
    return False


def _rect_tuple(rect) -> tuple[float, float, float, float] | None:
    if rect is None or rect.is_empty:
        return None
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def image_rms_difference(left: Path, right: Path) -> float:
    a = Image.open(left).convert("RGB")
    b = Image.open(right).convert("RGB").resize(a.size)
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    return sum(value**2 for value in stat.rms) ** 0.5
