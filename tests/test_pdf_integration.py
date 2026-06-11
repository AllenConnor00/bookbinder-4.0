from pathlib import Path

import pytest

from backend.bookbinder4.models import BindingMode, ImpositionSettings
from backend.bookbinder4 import pdf_engine
from backend.bookbinder4.pdf_engine import export_job, inspect_pdf, save_upload


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CANDIDATES = [
    ROOT / "Cottages and Cerberus Final.pdf",
    ROOT / "backend" / "data" / "uploads" / "5bee7ebb15e92c39-Cottages and Cerberus Final.pdf",
]
SAMPLE = next((path for path in SAMPLE_CANDIDATES if path.exists()), SAMPLE_CANDIDATES[0])


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample PDF not present")
def test_sample_pdf_plan_counts():
    data = SAMPLE.read_bytes()
    job_id, path = save_upload(SAMPLE.name, data)
    info = inspect_pdf(path, job_id)
    settings = ImpositionSettings(job_id=job_id, binding_mode=BindingMode.standard, standard_signature_folios=8, fidelity="vector", flyleaf_arrangement="none", front_flyleaf_leaves=0, back_flyleaf_leaves=0)
    result = export_job(settings)
    assert info.page_count == 309
    assert info.preflight
    assert result.plan.total_imposed_pages == 312
    assert result.plan.blank_pages == 3
    seen = sorted(slot.source_page for sheet in result.plan.sheets for side in (sheet.front, sheet.back) for slot in side if slot.source_page)
    assert seen == list(range(1, 310))
    assert result.output_paths


def _make_text_pdf(tmp_path: Path) -> Path:
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "text-only.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((36, 60), "Sharp vector text", fontsize=18)
    page.draw_line((36, 80), (240, 80), color=(0.1, 0.2, 0.8), width=0.8)
    doc.save(path)
    doc.close()
    return path


def test_auto_fidelity_keeps_text_only_pdf_vector(tmp_path):
    path = _make_text_pdf(tmp_path)
    job_id, _ = save_upload(path.name, path.read_bytes())

    settings = ImpositionSettings(job_id=job_id, fidelity="auto", split_output="combined", auto_validation_dpi=72)
    result = export_job(settings)

    assert result.export_report is not None
    assert result.export_report.total_slots == 1
    assert result.export_report.vector_slots == 1
    assert result.export_report.raster_slots == 0
    assert result.export_report.raster_fallback_pages == []


def test_auto_fidelity_manual_raster_override_is_slot_level(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = _make_text_pdf(tmp_path)
    job_id, _ = save_upload(path.name, path.read_bytes())

    settings = ImpositionSettings(job_id=job_id, fidelity="auto", split_output="combined", manual_raster_pages=[1])
    result = export_job(settings)

    assert result.export_report is not None
    assert result.export_report.vector_slots == 0
    assert result.export_report.raster_slots == 1
    assert result.export_report.raster_fallback_pages == [1]

    doc = fitz.open(result.output_paths[0])
    assert any(doc.load_page(index).get_images(full=True) for index in range(doc.page_count))
    doc.close()


def test_auto_fidelity_falls_back_when_diff_exceeds_threshold(tmp_path, monkeypatch):
    path = _make_text_pdf(tmp_path)
    job_id, _ = save_upload(path.name, path.read_bytes())
    monkeypatch.setattr(pdf_engine, "_compare_images", lambda reference, candidate, settings: settings.auto_diff_threshold + 1)

    settings = ImpositionSettings(job_id=job_id, fidelity="auto", split_output="combined", auto_validation_dpi=72)
    result = export_job(settings)

    assert result.export_report is not None
    assert result.export_report.vector_slots == 0
    assert result.export_report.raster_slots == 1
    assert result.export_report.decisions[0].reason == "auto validation exceeded threshold"
