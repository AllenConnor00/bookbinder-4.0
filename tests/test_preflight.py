"""Local, synthetic PDF tests for the read-only preflight API."""
from __future__ import annotations

import hashlib

import fitz
import pytest

from backend.bookbinder4.preflight import analyze_pdf, safe_job_path


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
