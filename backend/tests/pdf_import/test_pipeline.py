"""UC-87 — tầng lõi: tách từ, gán CEFR, gom chủ đề, điều phối.

Không test nào ở đây chạm pdfplumber/spaCy thật (xem `conftest.py`).
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import cefr, extractor, pipeline, tokenizer
from app.services.pdf_import.errors import LimitExceeded, NoTextFound

from .conftest import FakeNlp, make_document

SENTENCES = [
    "The forest absorbs carbon from the air.",
    "A healthy forest absorbs more carbon.",
    "Rivers carry sediment to the sea.",
]


@pytest.fixture
def fake_pdf(monkeypatch):
    """Thay pdfplumber bằng một tài liệu dựng sẵn."""

    def _install(sentences: list[str], *, page_count: int = 1):
        document = make_document(sentences, page_count=page_count)
        monkeypatch.setattr(
            extractor, "extract_document", lambda payload, *, max_pages: document
        )
        return document

    return _install


# ---------- Bước 2: tách & chuẩn hóa từ ----------


def test_tokenize_bo_stopword_va_gop_theo_lemma():
    nlp = FakeNlp()
    candidates = tokenizer.tokenize(SENTENCES, nlp)
    lemmas = {c.lemma for c in candidates}

    assert "the" not in lemmas and "from" not in lemmas   # stopword bị loại
    assert "absorb" in lemmas                             # absorbs -> absorb

    absorb = next(c for c in candidates if c.lemma == "absorb")
    assert absorb.occurrences == 2                        # gộp 2 câu thành 1 dòng


def test_tokenize_loai_ten_rieng_va_tu_qua_ngan():
    nlp = FakeNlp(pos={"Amazon": "PROPN", "air": "NOUN"})
    candidates = tokenizer.tokenize(["The Amazon forest holds air."], nlp)
    lemmas = {c.lemma for c in candidates}

    assert "amazon" not in lemmas    # PROPN: tên riêng là rác với người học từ vựng
    assert "air" in lemmas           # 3 ký tự vẫn đủ dài


def test_tokenize_dung_lemma_lam_tu_va_giu_dang_goc_de_doi_chieu():
    """Bộ từ phải chứa "absorb", không phải "absorbs" như tài liệu viết."""
    candidates = tokenizer.tokenize(SENTENCES, FakeNlp())
    absorb = next(c for c in candidates if c.lemma == "absorb")
    assert absorb.word == "absorb"
    assert absorb.surface_form == "absorbs"


def test_tokenize_lay_cau_dau_tien_lam_vi_du():
    """Bước 5 của N1 — câu ví dụ là câu GỐC trong tài liệu."""
    candidates = tokenizer.tokenize(SENTENCES, FakeNlp())
    absorb = next(c for c in candidates if c.lemma == "absorb")
    assert absorb.example_sentence == "The forest absorbs carbon from the air."


def test_tokenize_khong_co_cau_nao():
    assert tokenizer.tokenize([], FakeNlp()) == []
    assert tokenizer.tokenize(["   "], FakeNlp()) == []


# ---------- Bước 3: gán CEFR ----------


def test_tu_khong_co_trong_wordlist_thi_de_trong(fake_pdf, fake_nlp, fake_cefr):
    """BR-PDF-02 — không tra được thì để null, KHÔNG bịa."""
    fake_cefr({"forest": "A2"})
    fake_pdf(SENTENCES)

    result = pipeline.extract_candidates(b"%PDF-fake")
    levels = {c.lemma: c.cefr_level for c in result.candidates}

    assert levels["forest"] == "A2"
    assert levels["sediment"] is None          # có trong tài liệu, không có trong wordlist


def test_wordlist_that_doc_duoc():
    """Nguồn mặc định (CEFR-J) phải nạp được — thiếu nó là mất cột trình độ."""
    source = cefr.get_cefr_source()
    assert len(source) > 5000
    assert source.lookup("water") == "A1"
    assert source.lookup("Water") == "A1"      # tra không phân biệt hoa thường
    assert source.lookup("khongphaitienganh") is None


def test_tra_theo_tu_loai_phan_biet_duoc_nghia_khac_nhau():
    """"book" danh từ là A1, "book" động từ là B1 — bỏ từ loại là mất phân biệt."""
    source = cefr.get_cefr_source()
    assert source.lookup("book", "NOUN") == "A1"
    assert source.lookup("book", "VERB") == "B1"
    # Từ loại lạ (spaCy gán AUX/PROPN...) thì lùi về mức thấp nhất của từ đó
    assert source.lookup("book", "AUX") == "A1"


def test_thieu_file_wordlist_thi_no_chu_khong_im_lang(tmp_path):
    """Wordlist hỏng phải NỔ.

    Trả None cho mọi từ thì cột trình độ trắng bóc mà không ai biết tại sao —
    im lặng ở đây tốn hàng giờ dò lỗi.
    """
    with pytest.raises(FileNotFoundError):
        cefr.CsvCefrSource(tmp_path / "khong-ton-tai.csv")


def test_pipeline_doi_loi_wordlist_thanh_dependency_missing(monkeypatch):
    """Router cần 503 kèm cách dựng lại file, không phải 500 trơ."""
    from app.services.pdf_import.errors import DependencyMissing

    def _explode(_path=None):
        raise FileNotFoundError("Không thấy wordlist CEFR")

    monkeypatch.setattr(cefr, "get_cefr_source", _explode)

    with pytest.raises(DependencyMissing) as exc:
        pipeline.cefr_source()
    assert "build_cefr_wordlist" in str(exc.value)

    # health check thì báo 0 chứ không được nổ theo
    assert pipeline.cefr_source_info() == ("chưa nạp được", 0)


def test_loc_theo_muc_cefr_bo_luon_tu_khong_tra_duoc(fake_pdf, fake_nlp, fake_cefr):
    fake_cefr({"forest": "A2", "carbon": "B2"})
    fake_pdf(SENTENCES)

    result = pipeline.extract_candidates(b"%PDF-fake", cefr_levels=["A2"])
    assert [c.lemma for c in result.candidates] == ["forest"]
    assert result.total_words > 1              # tổng vẫn là số từ TRƯỚC khi lọc


# ---------- Bước 4: gom chủ đề (đường lùi) ----------


def test_llm_chet_thi_van_tra_ve_du_lieu_kem_canh_bao(fake_pdf, fake_nlp, fake_cefr):
    """BR-PDF-03 — Ollama chết KHÔNG được làm hỏng cả luồng.

    Không cần dựng gì thêm: `conftest` đã để Ollama ở trạng thái không chạy.
    """
    fake_cefr({"forest": "A2"})
    fake_pdf(SENTENCES)

    result = pipeline.extract_candidates(b"%PDF-fake")

    assert result.candidates                                  # vẫn có từ
    assert result.topics_available is False
    assert all(c.topic is None for c in result.candidates)
    assert any("chủ đề" in w for w in result.warnings)


def test_llm_song_thi_gan_chu_de(fake_pdf, fake_nlp, fake_cefr, monkeypatch):
    from app.speaking.scoring import ollama_client

    monkeypatch.setattr(
        ollama_client,
        "chat_json",
        lambda *a, **k: {"topics": {"forest": "Môi trường"}},
    )
    fake_cefr({})
    fake_pdf(SENTENCES)

    result = pipeline.extract_candidates(b"%PDF-fake")
    topics = {c.lemma: c.topic for c in result.candidates}
    assert topics["forest"] == "Môi trường"
    assert topics["sediment"] is None      # LLM không trả từ này -> để trống


def test_tag_topics_bo_qua_ket_qua_khong_phai_object(monkeypatch):
    """LLM trả JSON sai dạng cũng chỉ là 'không có chủ đề'."""
    from app.services.pdf_import import topic
    from app.speaking.scoring import ollama_client

    monkeypatch.setattr(ollama_client, "chat_json", lambda *a, **k: {"topics": "rác"})
    assert topic.tag_topics(["forest"]) == {}


# ---------- Giới hạn đầu vào ----------


def test_file_qua_lon_bi_chan():
    """E2 — giới hạn đọc từ system_configs, mặc định 10MB."""
    with pytest.raises(LimitExceeded) as exc:
        pipeline.extract_candidates(b"x" * (11 * 1024 * 1024))
    assert "10MB" in str(exc.value)


def test_gioi_han_lay_tu_cau_hinh_chu_khong_hardcode():
    from app.services import config_service

    config_service._cache = {"pdf_import_max_mb": "1"}
    try:
        with pytest.raises(LimitExceeded) as exc:
            pipeline.extract_candidates(b"x" * (2 * 1024 * 1024))
        assert "1MB" in str(exc.value)
    finally:
        config_service._cache = {}


def test_pdf_scan_anh_khong_trich_duoc_text(monkeypatch, fake_nlp):
    """E5 — bản scan không có lớp text."""
    def _no_text(payload, *, max_pages):
        raise NoTextFound("Không trích được chữ nào từ tài liệu.")

    monkeypatch.setattr(extractor, "extract_document", _no_text)
    with pytest.raises(NoTextFound):
        pipeline.extract_candidates(b"%PDF-fake")


def test_cat_bot_khi_qua_nhieu_tu(fake_pdf, fake_nlp, fake_cefr):
    from app.services import config_service

    fake_cefr({})
    fake_pdf(["Forest carbon sediment river mountain valley."])
    config_service._cache = {"pdf_import_max_words": "2"}
    try:
        result = pipeline.extract_candidates(b"%PDF-fake")
    finally:
        config_service._cache = {}

    assert len(result.candidates) == 2
    assert any("chỉ hiển thị 2 từ" in w for w in result.warnings)


def test_khong_con_tu_nao_sau_khi_loc_van_tra_200(fake_pdf, fake_nlp, fake_cefr):
    """E6 — danh sách rỗng + cảnh báo, không phải lỗi."""
    fake_cefr({})
    fake_pdf(SENTENCES)

    result = pipeline.extract_candidates(b"%PDF-fake", cefr_levels=["C2"])
    assert result.candidates == []
    assert any("Không còn từ nào" in w for w in result.warnings)
