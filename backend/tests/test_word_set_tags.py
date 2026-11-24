"""UC-96 — nhãn (tag) lọc chéo cho bộ từ vựng.

Nhãn khác danh mục (UC-76): danh mục do Admin quản lý và mỗi bộ đúng một; nhãn
do người tạo tự đặt, một bộ nhiều nhãn, dùng lọc chéo trình độ × mục tiêu ×
nguồn.

Điểm cần canh:
1. Chuẩn hóa — "IELTS", "ielts", " Ielts " phải về CÙNG một nhãn, nếu không bộ
   lọc đếm sai và người dùng không tìm thấy nhau.
2. Đếm nhãn chỉ tính bộ CÔNG KHAI — hiện một nhãn mà bấm vào ra rỗng là tệ hơn
   không hiện.
3. Tải bộ về phải chép cả nhãn (Q1: bản tải là snapshot).
"""
from __future__ import annotations

from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.models.word_set_tag import WordSetTag
from app.schemas.auth import RegisterRequest
from app.services import tag_service
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _public_set(db_session, owner, name, tags, *, public=True):
    ws = WordSet(owner_id=owner.id, name=name, category="G", difficulty="beginner",
                 is_public=public)
    db_session.add(ws)
    db_session.flush()
    db_session.add(Item(word_set_id=ws.id, word="w", meaning="m"))
    tag_service.set_tags(db_session, ws.id, tags)
    db_session.commit()
    return ws


# --- 1. Chuẩn hóa ------------------------------------------------------------

def test_chuan_hoa_ve_cung_mot_nhan():
    for raw in ("IELTS", "ielts", "  Ielts  ", "IELTS!!", "i e l t s"):
        assert tag_service.normalize(raw) in {"ielts", "i-e-l-t-s"}
    assert tag_service.normalize("IELTS Writing") == "ielts-writing"
    assert tag_service.normalize("oxford_3000") == "oxford-3000"


def test_bo_dau_tieng_viet_chu_khong_xoa_chu():
    """'tiếng anh' phải thành 'tieng-anh', không phải 'ting-anh'."""
    assert tag_service.normalize("Tiếng Anh") == "tieng-anh"
    assert tag_service.normalize("giao tiếp") == "giao-tiep"
    assert tag_service.normalize("Đại học") == "dai-hoc"


def test_nhan_rong_bi_loai_va_khong_trung_lap():
    assert tag_service.clean_tags(["", "  ", "!!!", "ielts", "IELTS"]) == ["ielts"]


def test_gioi_han_so_nhan_moi_bo():
    many = [f"tag{i}" for i in range(20)]
    assert len(tag_service.clean_tags(many)) == tag_service.MAX_TAGS_PER_SET


# --- 2. Gắn nhãn qua API ------------------------------------------------------

def test_tao_bo_tu_kem_nhan(client, db_session):
    _, headers = _user(db_session, "tg.a@example.com")
    body = client.post("/api/v1/word-sets", headers=headers, json={
        "name": "Bộ IELTS", "category": "G", "difficulty": "beginner",
        "tags": ["IELTS", "Học thuật", "ielts"],
    }).json()
    # đọc ra theo bảng chữ cái, không theo thứ tự nhập
    assert body["tags"] == ["hoc-thuat", "ielts"]


def test_sua_bo_tu_thay_toan_bo_nhan(client, db_session):
    user, headers = _user(db_session, "tg.b@example.com")
    ws = _public_set(db_session, user, "S", ["ielts", "b1"], public=False)

    body = client.patch(f"/api/v1/word-sets/{ws.id}", headers=headers, json={
        "name": "S", "category": "G", "difficulty": "beginner", "tags": ["toeic"],
    }).json()
    assert body["tags"] == ["toeic"]
    con_lai = db_session.query(WordSetTag).filter_by(word_set_id=ws.id).all()
    assert [t.tag for t in con_lai] == ["toeic"], "nhãn cũ phải bị gỡ, không cộng dồn"


def test_khong_gui_tags_thi_go_het(client, db_session):
    """`tags` vắng mặt = danh sách rỗng: đây là thao tác THAY TOÀN BỘ nhãn."""
    user, headers = _user(db_session, "tg.c@example.com")
    ws = _public_set(db_session, user, "S", ["ielts"], public=False)
    body = client.patch(f"/api/v1/word-sets/{ws.id}", headers=headers, json={
        "name": "S", "category": "G", "difficulty": "beginner",
    }).json()
    assert body["tags"] == []


# --- 3. Lọc & đếm ở Khám phá --------------------------------------------------

def test_loc_theo_nhan(client, db_session):
    owner, _ = _user(db_session, "tg.d@example.com")
    _, headers = _user(db_session, "tg.e@example.com")
    _public_set(db_session, owner, "Có IELTS", ["ielts", "b2"])
    _public_set(db_session, owner, "Chỉ TOEIC", ["toeic"])

    body = client.get("/api/v1/discover?tag=ielts", headers=headers).json()
    assert [i["name"] for i in body["items"]] == ["Có IELTS"]
    assert body["items"][0]["tags"] == ["b2", "ielts"]


def test_loc_khong_phan_biet_hoa_thuong(client, db_session):
    """Link chia sẻ '?tag=IELTS' phải ra cùng kết quả với '?tag=ielts'."""
    owner, _ = _user(db_session, "tg.f@example.com")
    _, headers = _user(db_session, "tg.g@example.com")
    _public_set(db_session, owner, "Bộ A", ["ielts"])

    hoa = client.get("/api/v1/discover?tag=IELTS", headers=headers).json()
    thuong = client.get("/api/v1/discover?tag=ielts", headers=headers).json()
    assert hoa["total"] == thuong["total"] == 1


def test_dem_nhan_chi_tinh_bo_cong_khai(client, db_session):
    owner, _ = _user(db_session, "tg.h@example.com")
    _, headers = _user(db_session, "tg.i@example.com")
    _public_set(db_session, owner, "Công khai", ["chung-nhan"])
    _public_set(db_session, owner, "Riêng tư", ["chung-nhan"], public=False)

    rows = client.get("/api/v1/discover/tags", headers=headers).json()
    found = {r["tag"]: r["count"] for r in rows}
    assert found.get("chung-nhan") == 1, "bộ riêng tư không được tính vào"


def test_nhan_khong_nuot_route_word_set_id(client, db_session):
    """'/discover/tags' phải là danh sách nhãn, không bị hiểu là id bộ từ."""
    _, headers = _user(db_session, "tg.j@example.com")
    resp = client.get("/api/v1/discover/tags", headers=headers)
    assert resp.status_code == 200 and isinstance(resp.json(), list)


# --- 4. Tải bộ về giữ nhãn ----------------------------------------------------

def test_tai_bo_ve_chep_ca_nhan(client, db_session):
    owner, _ = _user(db_session, "tg.k@example.com")
    _, headers = _user(db_session, "tg.l@example.com")
    ws = _public_set(db_session, owner, "Nguồn", ["ielts", "b1"])

    body = client.post(f"/api/v1/discover/{ws.id}/download", headers=headers).json()
    assert body["tags"] == ["b1", "ielts"]
