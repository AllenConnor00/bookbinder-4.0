from pathlib import Path

import pytest

from backend.bookbinder4.models import BindingMode, ImpositionSettings
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
    settings = ImpositionSettings(job_id=job_id, binding_mode=BindingMode.standard, standard_signature_folios=8, fidelity="vector")
    result = export_job(settings)
    assert info.page_count == 309
    assert info.preflight
    assert result.plan.total_imposed_pages == 312
    assert result.plan.blank_pages == 3
    seen = sorted(slot.source_page for sheet in result.plan.sheets for side in (sheet.front, sheet.back) for slot in side if slot.source_page)
    assert seen == list(range(1, 310))
    assert result.output_paths
