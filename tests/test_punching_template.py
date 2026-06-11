import pytest

from backend.bookbinder4.models import ImpositionSettings
from backend.bookbinder4.pdf_engine import PT_PER_IN, PT_PER_MM, create_punching_template, punching_template_info


def test_unit_conversion_constants():
    assert PT_PER_IN == 72
    assert PT_PER_MM == pytest.approx(72 / 25.4)


def test_sewing_station_positions_use_folded_signature_height():
    settings = ImpositionSettings(job_id="template-test")
    info = punching_template_info(settings)

    assert info.folded_signature_height_pt == 612
    assert info.station_positions[0].y_mm == pytest.approx(20)
    assert info.station_positions[-1].y_mm == pytest.approx((612 / PT_PER_MM) - 20)
    assert len(info.station_positions) == 5


def test_punching_template_dimensions_are_narrow_strip():
    settings = ImpositionSettings(job_id="template-test")
    info = punching_template_info(settings)

    assert info.width_mm == pytest.approx(45)
    assert info.height_pt == min(settings.paper.width, settings.paper.height)


def test_sewing_layout_presets_drive_station_counts():
    two_tape = ImpositionSettings(job_id="template-test", sewing_layout="two_tape", sewing_station_count=9)
    three_tape = ImpositionSettings(job_id="template-test", sewing_layout="three_tape", sewing_station_count=9)
    unsupported = ImpositionSettings(job_id="template-test", sewing_layout="unsupported_3", tape_supports=True, tape_count=3)

    assert len(punching_template_info(two_tape).station_positions) == 4
    assert len(punching_template_info(three_tape).station_positions) == 5
    assert len(punching_template_info(unsupported).station_positions) == 3


def test_calibration_page_accepts_duplex_flip_guidance():
    fitz = pytest.importorskip("fitz")
    settings = ImpositionSettings(job_id="template-test")
    from backend.bookbinder4.pdf_engine import create_calibration_page

    path = create_calibration_page(settings.paper, settings.print_safe_margin, "long")
    doc = fitz.open(path)
    text = doc.load_page(0).get_text()
    assert "flip on long edge" in text
    assert "Actual Size" in text
    doc.close()


def test_create_punching_template_pdf(tmp_path):
    fitz = pytest.importorskip("fitz")
    settings = ImpositionSettings(job_id="template-test", project_name="Template Test")
    path = create_punching_template(settings)

    doc = fitz.open(path)
    page = doc.load_page(0)
    info = punching_template_info(settings)
    assert doc.page_count == 1
    assert page.rect.width == pytest.approx(info.width_pt)
    assert page.rect.height == pytest.approx(info.height_pt)
    doc.close()
