"""UC-87 — hai bước qua API: trích/xem trước rồi mới ghi thư viện."""
from __future__ import annotations

import io
import sys

import pytest

from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.services.pdf_import import extractor
from app.services.pdf_import.errors import NoTextFound

from .conftest import make_document

EXTRACT_URL = "/api/v1/word-sets/extract-pdf"
CREATE_URL = "/api/v1/word-sets/from-pdf"
HEALTH_URL = "/api/v1/word-sets/pdf-import/health"

SENTENCES = [
    "The forest absorbs carbon from the air.",
    "A healthy forest absorbs more carbon.",
]


def _make_user(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(
            email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"
        ),
    )
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _upload(name: str = "giao-trinh.pdf", data: bytes = b"%PDF-1.4 fake"):
    return {"file": (name, io.BytesIO(data), "application/pdf")}


@pytest.fixture
def fake_pdf(monkeypatch):
    def _install(sentences: list[str], *, page_count: int = 2):
        document = make_document(sentences, page_count=page_count)
        monkeypatch.setattr(
            extractor, "extract_document", lambda payload, *, max_pages: document
        )

    return _install


# ---------- Bước 1: trích & xem trước ----------


def test_trich_pdf_tra_ve_ung_vien_va_khong_ghi_db(
    client, db_session, fake_pdf, fake_nlp, fake_cefr
):
    """BR-PDF-01 — bước xem trước tuyệt đối không chạm DB."""
    _, headers = _make_user(db_session, "uc87.a@example.com")
    fake_cefr({"forest": "A2", "carbon": "B2"})
    fake_pdf(SENTENCES)

    resp = client.post(EXTRACT_URL, files=_upload(), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["filename"] == "giao-trinh.pdf"
    assert body["page_count"] == 2
    by_lemma = {c["lemma"]: c for c in body["candidates"]}
    assert by_lemma["forest"]["cefr_level"] == "A2"
    assert by_lemma["forest"]["occurrences"] == 2
    assert by_lemma["forest"]["example_sentence"] == SENTENCES[0]
    assert by_lemma["air"]["cefr_level"] is None          # không có trong wordlist

    assert db_session.query(WordSet).count() == 0
    assert db_session.query(Item).count() == 0


def test_trich_pdf_loc_theo_muc_cefr(client, db_session, fake_pdf, fake_nlp, fake_cefr):
    _, headers = _make_user(db_session, "uc87.b@example.com")
    fake_cefr({"forest": "A2", "carbon": "B2"})
    fake_pdf(SENTENCES)

    resp = client.post(
        EXTRACT_URL, files=_upload(), data={"cefr_levels": "B2"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert [c["lemma"] for c in resp.json()["candidates"]] == ["carbon"]


def test_trich_pdf_khong_dang_nhap_thi_401(client, fake_nlp):
    assert client.post(EXTRACT_URL, files=_upload()).status_code == 401


def test_khong_phai_file_pdf_thi_422(client, db_session, fake_nlp):
    """E4 — chặn ngay ở đuôi file cho thông báo rõ ràng."""
    _, headers = _make_user(db_session, "uc87.c@example.com")
    resp = client.post(EXTRACT_URL, files=_upload("tu-vung.csv"), headers=headers)
    assert resp.status_code == 422
    assert ".pdf" in resp.json()["detail"]


def test_file_vuot_gioi_han_thi_413(client, db_session, fake_nlp):
    """E2 — 11MB vượt mặc định 10MB."""
    _, headers = _make_user(db_session, "uc87.d@example.com")
    resp = client.post(
        EXTRACT_URL, files=_upload(data=b"x" * (11 * 1024 * 1024)), headers=headers
    )
    assert resp.status_code == 413
    assert "10MB" in resp.json()["detail"]


def test_pdf_scan_anh_thi_422_kem_goi_y_ocr(client, db_session, monkeypatch, fake_nlp):
    """E5 — bản scan ảnh không có lớp text."""
    _, headers = _make_user(db_session, "uc87.e@example.com")

    def _no_text(payload, *, max_pages):
        raise NoTextFound("Không trích được chữ nào từ tài liệu. Bản scan ảnh — cần OCR.")

    monkeypatch.setattr(extractor, "extract_document", _no_text)

    resp = client.post(EXTRACT_URL, files=_upload(), headers=headers)
    assert resp.status_code == 422
    assert "OCR" in resp.json()["detail"]


def test_chua_cai_thu_vien_thi_503_kem_huong_dan(client, db_session, monkeypatch):
    """E1 — thiếu phụ thuộc chỉ làm hỏng UC-87, phần còn lại của app vẫn chạy."""
    _, headers = _make_user(db_session, "uc87.f@example.com")
    monkeypatch.setitem(sys.modules, "pdfplumber", None)

    resp = client.post(EXTRACT_URL, files=_upload(), headers=headers)
    assert resp.status_code == 503
    assert "requirements-import.txt" in resp.json()["detail"]

    # Phần còn lại của ứng dụng không bị ảnh hưởng
    assert client.get("/api/v1/word-sets", headers=headers).status_code == 200


# ---------- Bước 2: xác nhận & tạo bộ từ ----------


def test_tao_bo_tu_tu_danh_sach_da_duyet(client, db_session):
    _, headers = _make_user(db_session, "uc87.g@example.com")

    payload = {
        "name": "Từ vựng môi trường",
        "description": "Cắt từ giáo trình",
        "category": "Khoa học",
        "difficulty": "intermediate",
        "source_filename": "giao-trinh.pdf",
        "words": [
            {
                "word": "forest", "lemma": "forest", "part_of_speech": "noun",
                "meaning": "rừng", "example": SENTENCES[0], "cefr_level": "A2",
                "topic": "Môi trường",
            },
            {"word": "carbon", "meaning": "các-bon"},
        ],
    }
    resp = client.post(CREATE_URL, json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Từ vựng môi trường"
    assert body["item_count"] == 2

    word_set = db_session.get(WordSet, body["id"])
    assert word_set.source == "pdf"                       # BR-PDF-05
    assert word_set.source_filename == "giao-trinh.pdf"

    items = db_session.query(Item).filter(Item.word_set_id == word_set.id).all()
    forest = next(i for i in items if i.word == "forest")
    assert forest.meaning == "rừng"
    assert forest.example == SENTENCES[0]
    assert forest.part_of_speech == "noun"


def test_tao_bo_tu_khu_trung_lap_theo_mat_chu(client, db_session):
    _, headers = _make_user(db_session, "uc87.h@example.com")
    resp = client.post(
        CREATE_URL,
        json={
            "name": "Bộ trùng",
            "words": [
                {"word": "forest", "meaning": "rừng"},
                {"word": "Forest", "meaning": "rừng (trùng)"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["item_count"] == 1


def test_de_trong_nghia_van_tao_duoc(client, db_session):
    """BR-PDF-06 — hệ thống không tự dịch; người học bổ sung sau ở UC-14."""
    _, headers = _make_user(db_session, "uc87.i@example.com")
    resp = client.post(
        CREATE_URL,
        json={"name": "Chưa dịch", "words": [{"word": "sediment"}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    item = db_session.query(Item).filter(Item.word == "sediment").one()
    assert item.meaning == ""


def test_danh_sach_tu_rong_thi_400(client, db_session):
    """E8 — không có từ nào thì không tạo bộ từ rỗng."""
    _, headers = _make_user(db_session, "uc87.j@example.com")
    resp = client.post(CREATE_URL, json={"name": "Bộ rỗng", "words": []}, headers=headers)
    assert resp.status_code == 400
    assert db_session.query(WordSet).count() == 0


def test_danh_sach_toan_khoang_trang_thi_400(client, db_session):
    _, headers = _make_user(db_session, "uc87.k@example.com")
    resp = client.post(
        CREATE_URL,
        json={"name": "Bộ rỗng", "words": [{"word": "   "}]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert db_session.query(WordSet).count() == 0


# ---------- Health ----------


def test_health_bao_trang_thai_tung_phu_thuoc(client, db_session):
    _, headers = _make_user(db_session, "uc87.l@example.com")
    resp = client.get(HEALTH_URL, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert {d["name"] for d in body["dependencies"]} == {
        "pdfplumber", "spacy", "cefr_wordlist", "ollama",
    }
    assert body["max_file_mb"] == 10
    assert body["max_pages"] == 50
    assert body["cefr_source"] == "cefrj+octanove"
    assert body["cefr_word_count"] > 5000          # wordlist chuẩn nạp được
    for dependency in body["dependencies"]:
        if not dependency["ready"]:
            assert dependency["detail"]            # chưa sẵn sàng thì phải nói cách sửa
