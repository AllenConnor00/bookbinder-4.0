"""Read-only per-page PDF preflight; never mutates the source document."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from pydantic import BaseModel, Field

from .pdf_engine import require_fitz

_JOB_ID = re.compile(r"^[a-f0-9]{16}$")


class Finding(BaseModel):
    severity: str
    code: str
    detail: str


class ImagePlacement(BaseModel):
    xref: int
    width_px: int
    height_px: int
    displayed_width_pt: float
    displayed_height_pt: float
    effective_dpi_x: float
    effective_dpi_y: float


class PageReport(BaseModel):
    page_number: int
    width_pt: float
    height_pt: float
    rotation: int
    text_chars: int
    image_count: int
    link_count: int
    annotation_count: int
    blank_candidate: bool
    text_classification: str
    images: list[ImagePlacement] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


class PreflightReport(BaseModel):
    schema_version: int = 1
    job_id: str
    source_sha256: str
    total_pages: int
    start_page: int
    end_page: int
    target_width_pt: float
    target_height_pt: float
    pages: list[PageReport]


def safe_job_path(job_id: str, upload_dir: Path) -> Path:
    if not _JOB_ID.fullmatch(job_id):
        raise ValueError("Invalid job ID.")
    matches = sorted(upload_dir.glob(f"{job_id}-*"))
    if not matches:
        raise FileNotFoundError("PDF job not found.")
    candidate = matches[0].resolve()
    if not candidate.is_relative_to(upload_dir.resolve()) or not candidate.is_file():
        raise ValueError("Invalid PDF job path.")
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def effective_image_dpi(width_px: int, height_px: int, width_pt: float, height_pt: float) -> tuple[float, float]:
    if width_px <= 0 or height_px <= 0 or width_pt <= 0 or height_pt <= 0:
        raise ValueError("Image pixel and placement dimensions must be positive.")
    return width_px * 72 / width_pt, height_px * 72 / height_pt


def _page_report(page, number: int, target_width_pt: float, target_height_pt: float) -> PageReport:
    # The same aspect-preserving 'fit' geometry as a normalized interior.
    source = page.rect
    factor = min(target_width_pt / source.width, target_height_pt / source.height)
    text = page.get_text("text")
    drawings = page.get_drawings()
    images: list[ImagePlacement] = []
    findings: list[Finding] = []
    for info in page.get_images(full=True):
        xref = info[0]
        width_px, height_px = int(info[2]), int(info[3])
        for rect in page.get_image_rects(xref):
            if rect.is_empty or rect.width <= 0 or rect.height <= 0:
                continue
            width_pt, height_pt = rect.width * factor, rect.height * factor
            dpi_x, dpi_y = effective_image_dpi(width_px, height_px, width_pt, height_pt)
            images.append(ImagePlacement(
                xref=xref, width_px=width_px, height_px=height_px,
                displayed_width_pt=round(width_pt, 2), displayed_height_pt=round(height_pt, 2),
                effective_dpi_x=round(dpi_x, 1), effective_dpi_y=round(dpi_y, 1),
            ))
            if min(dpi_x, dpi_y) < 200:
                findings.append(Finding(severity="warning", code="low_image_dpi",
                                        detail=f"Image {xref}: {min(dpi_x, dpi_y):.0f} effective DPI at target size."))
    links = page.get_links()
    annotations = list(page.annots() or [])
    if links:
        findings.append(Finding(severity="info", code="links", detail=f"{len(links)} link(s) present; appearance may be baked into page content."))
    if source.width > target_width_pt or source.height > target_height_pt:
        findings.append(Finding(severity="info", code="scaled_to_fit", detail="Page will be scaled down to fit target dimensions."))
    # Extracted text may be an invisible OCR layer. Never assert it is vector glyph text.
    classification = "text_layer_present_unverified" if text.strip() else ("image_only_or_graphics" if images or drawings else "no_extracted_text")
    blank = not text.strip() and not images and not drawings
    return PageReport(
        page_number=number, width_pt=round(source.width, 2), height_pt=round(source.height, 2),
        rotation=page.rotation, text_chars=len(text.strip()), image_count=len(images),
        link_count=len(links), annotation_count=len(annotations),
        blank_candidate=blank, text_classification=classification,
        images=images, findings=findings,
    )


def analyze_pdf(path: Path, job_id: str, start_page: int = 1, limit: int = 25,
                target_width_pt: float = 396, target_height_pt: float = 612) -> PreflightReport:
    if start_page < 1 or not 1 <= limit <= 100:
        raise ValueError("start_page must be >= 1 and limit must be 1..100.")
    if not all(math.isfinite(v) and 36 <= v <= 2000 for v in (target_width_pt, target_height_pt)):
        raise ValueError("Target dimensions must be finite and between 36 and 2000 points.")
    pdf = require_fitz()
    source_hash = sha256_file(path)
    with pdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("Encrypted PDF cannot be inspected without a password.")
        total = doc.page_count
        if start_page > total:
            raise ValueError("start_page exceeds PDF page count.")
        end = min(total, start_page + limit - 1)
        pages = [_page_report(doc.load_page(i - 1), i, target_width_pt, target_height_pt)
                 for i in range(start_page, end + 1)]
    return PreflightReport(job_id=job_id, source_sha256=source_hash, total_pages=total,
                           start_page=start_page, end_page=end,
                           target_width_pt=target_width_pt, target_height_pt=target_height_pt, pages=pages)
