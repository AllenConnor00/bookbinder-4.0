"""Local, synthetic PDF tests for the read-only preflight API."""
from __future__ import annotations

import hashlib

import fitz
import pytest

from backend.bookbinder4.preflight import analyze_pdf, effective_image_dpi, safe_job_path, sha256_file


def make_pdf(path):
    doc = fitz.open()
    page = doc.new_page(width=396, height=612)
    page.insert_text((40, 60), "Vector text", fontsize=12)
    page.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(35, 40, 120, 65), "uri": "https://example.org"})
    doc.new_page(width=396, height=612)
    doc.new_page(width=396, height=612)
    doc.save(path)
    doc.close()


def test_page_inventory_and_source_immutability(tmp_path):
    path = tmp_path / "source.pdf"
    make_pdf(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    report = analyze_pdf(path, "test", start_page=1, limit=2)
    assert report.total_pages == 3
    assert [p.page_number for p in report.pages] == [1, 2]
    assert report.pages[0].text_chars > 0
    assert report.pages[0].link_count == 1
    assert report.pages[0].text_classification == "text_layer_present_unverified"
    assert report.pages[1].blank_candidate
    assert report.source_sha256 == before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_pagination_beyond_twenty_pages(tmp_path):
    path = tmp_path / "many.pdf"
    doc = fitz.open()
    for _ in range(24):
        doc.new_page(width=396, height=612)
    doc.save(path)
    doc.close()
    report = analyze_pdf(path, "test", start_page=21, limit=4)
    assert [p.page_number for p in report.pages] == [21, 22, 23, 24]


def test_job_id_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_job_path("../../etc/passwd", tmp_path)


def test_invalid_range_rejected(tmp_path):
    path = tmp_path / "source.pdf"
    make_pdf(path)
    with pytest.raises(ValueError):
        analyze_pdf(path, "test", start_page=0)
    with pytest.raises(ValueError):
        analyze_pdf(path, "test", limit=101)


def test_effective_dpi_uses_final_placement_not_pdf_metadata():
    x, y = effective_image_dpi(1484, 1920, 396, 612)
    assert x == pytest.approx(269.81818, rel=1e-4)
    assert y == pytest.approx(225.88235, rel=1e-4)
    with pytest.raises(ValueError):
        effective_image_dpi(1484, 1920, 0, 612)


def test_image_placement_dpi_and_warning(tmp_path):
    from PIL import Image
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    path = tmp_path / "raster.pdf"
    doc = fitz.open()
    page = doc.new_page(width=396, height=612)
    page.insert_image(fitz.Rect(0, 0, 396, 612), stream=buffer.getvalue())
    doc.save(path)
    doc.close()

    report = analyze_pdf(path, "test")
    page_report = report.pages[0]
    assert page_report.image_count == 1
    assert page_report.images[0].effective_dpi_x == pytest.approx(18.2, abs=0.1)
    assert page_report.images[0].effective_dpi_y == pytest.approx(11.8, abs=0.1)
    assert any(f.code == "low_image_dpi" for f in page_report.findings)


def test_streamed_hash_matches_standard_digest(tmp_path):
    path = tmp_path / "large.bin"
    path.write_bytes(b"abcdef" * 200000)
    assert sha256_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_rejects_nonfinite_target_dimensions(tmp_path):
    path = tmp_path / "source.pdf"
    make_pdf(path)
    with pytest.raises(ValueError):
        analyze_pdf(path, "test", target_width_pt=float("nan"))


def test_rotated_image_uses_transform_axes_not_bbox(tmp_path):
    from io import BytesIO
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (200, 100), "black").save(buffer, format="PNG")
    path = tmp_path / "rotated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=396, height=612)
    page.insert_image(fitz.Rect(30, 30, 130, 230), stream=buffer.getvalue(), rotate=90)
    doc.save(path)
    doc.close()

    result = analyze_pdf(path, "test")
    image = result.pages[0].images[0]
    assert image.width_px == 200
    assert image.height_px == 100
    assert image.effective_dpi_x > 0
    assert image.effective_dpi_y > 0
    # The rotation-aware dimensions must not simply be the bbox dimensions.
    assert image.displayed_width_pt != pytest.approx(100)
