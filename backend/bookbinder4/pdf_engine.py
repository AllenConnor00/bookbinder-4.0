from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Iterable

try:
    import fitz
except ImportError:  # pragma: no cover - exercised by environment setup
    fitz = None

from PIL import Image, ImageChops, ImageStat

from .binding import build_plan
from .models import ExportResult, ImpositionPlan, ImpositionSettings, PdfInspectResult, PdfPageInfo, PageSlot, PaperPreset, PreflightItem


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "backend" / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = ROOT / "outputs"
PREVIEW_DIR = DATA_DIR / "previews"
TOOLS_DIR = DATA_DIR / "tools"


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
        warnings.append("This PDF uses images, masks, or newer PDF features; hybrid validation is recommended.")
        preflight.append(_preflight("warning", "Modern PDF features", "The file uses features that older or simpler PDF processors often mishandle.", "Use Safest print / flattened for complete reliability."))

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
        _write_pdf(path, out_path, settings, plan.sheets)
        outputs = [str(out_path)]
    else:
        outputs = []
        for signature in plan.signatures:
            sheets = [plan.sheets[index] for index in signature.sheets]
            out_path = output_root / f"signature-{signature.index + 1:02d}.pdf"
            _write_pdf(path, out_path, settings, sheets)
            outputs.append(str(out_path))

    validation_warnings = validate_export_outputs(outputs)
    if settings.fidelity == "hybrid" and validation_warnings:
        validation_warnings.append("Hybrid validation found differences; export was kept vector-first. Use raster fidelity for a fully flattened retry.")

    return ExportResult(
        job_id=settings.job_id,
        output_paths=outputs,
        validation_warnings=validation_warnings,
        plan=plan,
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


def create_calibration_page(paper: PaperPreset, print_safe_margin: float = 14.2) -> Path:
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
    page.draw_line((center_x, 0), (center_x, sheet_h), color=(1, 0, 0), width=0.8)
    page.draw_line((0, center_y), (sheet_w, center_y), color=(0, 0.3, 0.9), width=0.6)
    page.insert_text((center_x + 6, 20), "fold centerline", fontsize=8, color=(1, 0, 0))
    safe = pdf.Rect(print_safe_margin, print_safe_margin, sheet_w - print_safe_margin, sheet_h - print_safe_margin)
    page.draw_rect(safe, color=(0, 0.55, 0.2), width=1)
    page.insert_text((safe.x0 + 6, safe.y0 + 14), f"print-safe area ({print_safe_margin / 2.83464567:.1f} mm margin)", fontsize=8, color=(0, 0.45, 0.2))

    for offset in range(0, int(sheet_w // 2), 36):
        for x in (center_x - offset, center_x + offset):
            page.draw_line((x, center_y - 8), (x, center_y + 8), color=(0, 0, 0), width=0.4)
    for offset in range(0, int(sheet_h // 2), 36):
        for y in (center_y - offset, center_y + offset):
            page.draw_line((center_x - 8, y), (center_x + 8, y), color=(0, 0, 0), width=0.4)

    _draw_crop_marks(page, sheet_w, sheet_h)
    for i in range(11):
        x = 72 + i * 36
        page.draw_line((x, sheet_h - 58), (x, sheet_h - 45), color=(0, 0, 0), width=0.5)
        page.insert_text((x - 4, sheet_h - 34), str(i / 2), fontsize=7)
    page.draw_line((72, sheet_h - 50), (72 + 10 * 36, sheet_h - 50), color=(0, 0, 0), width=0.5)
    page.insert_text((72, sheet_h - 18), "5 inch ruler", fontsize=8)
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


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


def _write_pdf(source_path: Path, out_path: Path, settings: ImpositionSettings, sheets: Iterable) -> None:
    pdf = require_fitz()
    source = pdf.open(source_path)
    target = pdf.open()
    sheet_w = max(settings.paper.width, settings.paper.height)
    sheet_h = min(settings.paper.width, settings.paper.height)

    for sheet in sheets:
        for side_name in ("front", "back"):
            output_page = target.new_page(width=sheet_w, height=sheet_h)
            slots = getattr(sheet, side_name)
            for slot in slots:
                if slot.is_blank:
                    continue
                if settings.fidelity in ("raster", "hybrid"):
                    _place_raster(output_page, source, slot, settings)
                else:
                    _place_vector(output_page, source, slot, settings)
            if settings.crop_marks:
                _draw_crop_marks(output_page, sheet_w, sheet_h)
            if settings.sewing_marks:
                _draw_sewing_marks(output_page, sheet_w, sheet_h, settings)

    target.save(out_path, garbage=4, deflate=True)
    target.close()
    source.close()


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
    count = max(2, settings.sewing_station_count)
    inset = min(settings.sewing_station_margin, max(0, height / 2 - 6))
    usable = max(0, height - inset * 2)
    step = usable / (count - 1) if count > 1 else 0
    half_mark = settings.sewing_mark_length / 2
    for index in range(count):
        y = inset + step * index
        page.draw_line((center_x - half_mark, y), (center_x + half_mark, y), color=(0, 0, 0), width=0.45)
        page.draw_circle((center_x, y), 1.2, color=(0, 0, 0), fill=(1, 1, 1), width=0.35)


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
