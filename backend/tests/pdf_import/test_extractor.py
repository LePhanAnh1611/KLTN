"""UC-87 bước 1 — trích văn bản & giữ ranh giới câu."""
from __future__ import annotations

import sys

import pytest

from app.services.pdf_import import extractor
from app.services.pdf_import.errors import DependencyMissing, InvalidPdf


def test_split_sentences_giu_tung_cau():
    text = "Photosynthesis feeds the plant. Chlorophyll absorbs light! Does it work?"
    assert extractor.split_sentences(text) == [
        "Photosynthesis feeds the plant.",
        "Chlorophyll absorbs light!",
        "Does it work?",
    ]


def test_split_sentences_noi_lai_dong_bi_xuong_hang():
    """PDF xuống dòng theo chiều rộng trang, không theo câu."""
    text = "The mitochondrion is the\npowerhouse of the cell.\nIt makes energy."
    assert extractor.split_sentences(text) == [
        "The mitochondrion is the powerhouse of the cell.",
        "It makes energy.",
    ]


def test_tieu_de_khong_bi_dan_vao_cau_ke_tiep():
    """Dòng sau bắt đầu bằng chữ hoa -> dòng trước là tiêu đề, không phải câu dở."""
    text = "Climate and the Carbon Cycle\nThe forest absorbs carbon."
    assert extractor.split_sentences(text) == [
        "Climate and the Carbon Cycle",
        "The forest absorbs carbon.",
    ]


def test_split_sentences_noi_lai_tu_bi_gach_noi_cuoi_dong():
    text = "We need more informa-\ntion about it."
    assert extractor.split_sentences(text) == ["We need more information about it."]


def test_split_sentences_text_rong():
    assert extractor.split_sentences("") == []
    assert extractor.split_sentences("   \n  ") == []


def test_thieu_pdfplumber_thi_bao_dependency_missing(monkeypatch):
    """E1 — chưa cài thư viện thì nói rõ cách cài, không nổ ImportError thô."""
    monkeypatch.setitem(sys.modules, "pdfplumber", None)
    with pytest.raises(DependencyMissing) as exc:
        extractor.extract_document(b"%PDF-1.4", max_pages=50)
    assert "requirements-import.txt" in str(exc.value)


def test_file_rong_la_pdf_khong_hop_le():
    """File rỗng phải báo lỗi đầu vào, không phải lỗi thiếu thư viện."""
    with pytest.raises(InvalidPdf):
        extractor.extract_document(b"", max_pages=50)
