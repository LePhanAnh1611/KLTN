"""UC-95 — tra cứu từ.

Đây là tra trong KHO DỮ LIỆU HỆ THỐNG, không phải từ điển đầy đủ. Điểm cần canh:

1. Không rò bộ riêng tư của người khác qua đường tra từ.
2. Không tìm thấy → **200 kèm gợi ý**, không phải 404: phép tra đã chạy xong,
   chỉ là kết quả rỗng, và giao diện cần phân biệt hai chuyện đó.
3. Nghĩa trong thư viện của chính người tra phải lên trước nghĩa của cộng đồng.
"""
from __future__ import annotations

from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import dictionary_service
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _set_with(db_session, owner, name, words, *, public=False, downloads=0):
    ws = WordSet(owner_id=owner.id, name=name, category="G", difficulty="beginner",
                 is_public=public, download_count=downloads)
    db_session.add(ws)
    db_session.flush()
    for w in words:
        db_session.add(Item(word_set_id=ws.id, **w))
    db_session.commit()
    return ws


# --- Chuẩn hóa ----------------------------------------------------------------

def test_chuan_hoa_chuoi_tra():
    assert dictionary_service.normalize_query("  Habitat!! ") == "habitat"
    assert dictionary_service.normalize_query("HABITAT") == "habitat"
    assert dictionary_service.normalize_query("ice   cream") == "ice cream"
    assert dictionary_service.normalize_query("123") == ""


# --- Kết quả ------------------------------------------------------------------

def test_tra_duoc_tu_trong_thu_vien_cua_minh(client, db_session):
    user, headers = _user(db_session, "dic.a@example.com")
    _set_with(db_session, user, "Bộ của tôi", [
        {"word": "habitat", "meaning": "môi trường sống", "part_of_speech": "noun",
         "phonetic": "/ˈhæbɪtæt/", "example": "A natural habitat."},
    ])

    body = client.get("/api/v1/dictionary?q=Habitat", headers=headers).json()
    assert body["query"] == "habitat"
    assert body["in_my_library"] is True
    assert len(body["entries"]) == 1
    e = body["entries"][0]
    assert e["meaning"] == "môi trường sống"
    assert e["phonetic"] == "/ˈhæbɪtæt/"
    assert e["word_set_name"] == "Bộ của tôi"
    assert e["in_my_library"] is True


def test_tra_duoc_tu_trong_bo_cong_khai_cua_nguoi_khac(client, db_session):
    owner, _ = _user(db_session, "dic.b1@example.com")
    _, headers = _user(db_session, "dic.b2@example.com")
    _set_with(db_session, owner, "Bộ cộng đồng", [
        {"word": "drought", "meaning": "hạn hán"},
    ], public=True)

    body = client.get("/api/v1/dictionary?q=drought", headers=headers).json()
    assert [e["meaning"] for e in body["entries"]] == ["hạn hán"]
    assert body["in_my_library"] is False, "từ của người khác không phải thư viện của mình"


def test_khong_ro_bo_rieng_tu_cua_nguoi_khac(client, db_session):
    owner, _ = _user(db_session, "dic.c1@example.com")
    _, headers = _user(db_session, "dic.c2@example.com")
    _set_with(db_session, owner, "Bộ riêng", [
        {"word": "secretword", "meaning": "không được lộ"},
    ], public=False)

    body = client.get("/api/v1/dictionary?q=secretword", headers=headers).json()
    assert body["entries"] == []


def test_nghia_cua_minh_len_truoc_nghia_cong_dong(client, db_session):
    user, headers = _user(db_session, "dic.d1@example.com")
    other, _ = _user(db_session, "dic.d2@example.com")
    _set_with(db_session, other, "Bộ nổi tiếng", [
        {"word": "policy", "meaning": "chính sách (cộng đồng)"},
    ], public=True, downloads=999)
    _set_with(db_session, user, "Bộ của tôi", [
        {"word": "policy", "meaning": "chính sách (của tôi)"},
    ])

    entries = client.get("/api/v1/dictionary?q=policy", headers=headers).json()["entries"]
    assert entries[0]["meaning"] == "chính sách (của tôi)"
    assert entries[0]["in_my_library"] is True


def test_khong_tim_thay_thi_200_kem_goi_y_chu_khong_404(client, db_session):
    user, headers = _user(db_session, "dic.e@example.com")
    _set_with(db_session, user, "Bộ", [
        {"word": "environment", "meaning": "môi trường"},
        {"word": "environmental", "meaning": "thuộc môi trường"},
    ])

    resp = client.get("/api/v1/dictionary?q=environme", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert "environment" in body["suggestions"]


def test_co_ket_qua_thi_khong_kem_goi_y(client, db_session):
    """Gợi ý chỉ để cứu ca trượt; có kết quả rồi mà còn gợi ý là nhiễu."""
    user, headers = _user(db_session, "dic.f@example.com")
    _set_with(db_session, user, "Bộ", [
        {"word": "flood", "meaning": "lũ lụt"},
        {"word": "flooding", "meaning": "ngập"},
    ])
    body = client.get("/api/v1/dictionary?q=flood", headers=headers).json()
    assert body["entries"] and body["suggestions"] == []


def test_khu_trung_nghia_lap_lai_o_nhieu_bo(client, db_session):
    """Bộ tải về là bản sao (Q1), nên cùng một nghĩa sẽ lặp ở nhiều bộ."""
    user, headers = _user(db_session, "dic.g@example.com")
    for i in range(3):
        _set_with(db_session, user, f"Bộ {i}", [
            {"word": "reform", "meaning": "cải cách", "part_of_speech": "noun"},
        ])
    entries = client.get("/api/v1/dictionary?q=reform", headers=headers).json()["entries"]
    assert len(entries) == 1


def test_bo_da_xoa_mem_khong_hien(client, db_session):
    from datetime import datetime, timezone
    user, headers = _user(db_session, "dic.h@example.com")
    ws = _set_with(db_session, user, "Bộ đã xóa", [{"word": "gone", "meaning": "mất"}])
    ws.deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    body = client.get("/api/v1/dictionary?q=gone", headers=headers).json()
    assert body["entries"] == []


def test_muc_cefr_lay_tu_wordlist_chuan(client, db_session):
    """Mức CEFR không phụ thuộc vào việc từ đó có trong bộ nào hay không."""
    _, headers = _user(db_session, "dic.i@example.com")
    body = client.get("/api/v1/dictionary?q=book", headers=headers).json()
    assert body["cefr_level"] in {"A1", "A2", "B1", "B2", "C1", "C2"}


def test_yeu_cau_dang_nhap(client):
    assert client.get("/api/v1/dictionary?q=book").status_code == 401


def test_thieu_tham_so_thi_422(client, db_session):
    _, headers = _user(db_session, "dic.j@example.com")
    assert client.get("/api/v1/dictionary", headers=headers).status_code == 422
