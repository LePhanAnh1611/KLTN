"""UC-81 cấu hình hệ thống · UC-75 quản lý kho bộ từ (Admin)."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service
from app.services.auth_service import register_user


def _user(db_session, email, role="learner"):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    if role != "learner":
        u.role = role
        db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _word_set(db_session, owner_id, name, n_items=2, is_public=True):
    ws = WordSet(owner_id=owner_id, name=name, is_public=is_public,
                 category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    db_session.add_all([Item(word_set_id=ws.id, word=f"w{i}", meaning=f"m{i}") for i in range(n_items)])
    db_session.commit()
    db_session.refresh(ws)
    return ws


# --- UC-81 -------------------------------------------------------------------

def test_list_config_returns_defaults(client, db_session):
    _, headers = _user(db_session, "cf.a@example.com", role="admin")

    items = client.get("/api/v1/admin/config", headers=headers).json()
    by_key = {c["key"]: c for c in items}
    assert by_key["review_threshold"]["value"] == 0.6
    assert by_key["xp_per_correct"]["value"] == 10
    assert by_key["require_post_approval"]["value"] is False
    assert by_key["mastered_threshold"]["minimum"] == 0.5


def test_update_config_applies_immediately(client, db_session):
    """UC-81 bước 2 — lưu xong áp dụng ngay cho UC-46 (XP) và UC-66 (lịch ôn)."""
    _, headers = _user(db_session, "cf.b@example.com", role="admin")
    from app.services import gamification_service, review_service

    assert gamification_service.xp_per_correct() == 10
    assert review_service.mastery_to_interval_days(0.65) == 2

    r = client.put("/api/v1/admin/config", headers=headers,
                   json={"values": {"xp_per_correct": 20, "review_threshold": 0.7}})
    assert r.status_code == 200

    assert gamification_service.xp_per_correct() == 20
    # θ_review lên 0.7 -> mastery 0.65 giờ bị coi là "chưa nắm" -> ôn ngày mai
    assert review_service.mastery_to_interval_days(0.65) == 1


def test_update_config_writes_audit(client, db_session):
    admin, headers = _user(db_session, "cf.c@example.com", role="admin")
    client.put("/api/v1/admin/config", headers=headers,
               json={"values": {"xp_per_level": 200}})

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "config.update")
    ).scalars().one()
    assert entry.actor_id == admin.id and "xp_per_level: 100 -> 200" in entry.detail


def test_update_config_out_of_range_rejected(client, db_session):
    """UC-81 E1 — giá trị ngoài khoảng an toàn bị chặn, không lưu."""
    _, headers = _user(db_session, "cf.d@example.com", role="admin")

    r = client.put("/api/v1/admin/config", headers=headers,
                   json={"values": {"mastered_threshold": 1.5}})
    assert r.status_code == 400
    assert config_service.get_float("mastered_threshold") == 0.9

    r = client.put("/api/v1/admin/config", headers=headers,
                   json={"values": {"band_low": 0.9, "band_high": 0.8}})
    assert r.status_code == 400
    assert config_service.get_float("band_low") == 0.6


def test_update_unknown_config_key_rejected(client, db_session):
    _, headers = _user(db_session, "cf.e@example.com", role="admin")
    r = client.put("/api/v1/admin/config", headers=headers,
                   json={"values": {"khong_ton_tai": 1}})
    assert r.status_code == 400


def test_config_requires_admin(client, db_session):
    _, learner = _user(db_session, "cf.f@example.com")
    assert client.get("/api/v1/admin/config", headers=learner).status_code == 403
    assert client.put("/api/v1/admin/config", headers=learner,
                      json={"values": {"xp_per_correct": 5}}).status_code == 403


def test_min_items_to_publish_from_config(client, db_session):
    """Ngưỡng publish (UC-17) giờ lấy từ cấu hình chứ không hardcode."""
    admin, admin_headers = _user(db_session, "cf.g1@example.com", role="admin")
    owner, owner_headers = _user(db_session, "cf.g2@example.com")
    ws = _word_set(db_session, owner.id, "Bộ 2 từ", n_items=2, is_public=False)

    client.put("/api/v1/admin/config", headers=admin_headers,
               json={"values": {"min_items_to_publish": 5}})

    r = client.patch(f"/api/v1/word-sets/{ws.id}/publish",
                     json={"is_public": True}, headers=owner_headers)
    assert r.status_code == 400 and "tối thiểu 5 từ" in r.json()["detail"]


# --- UC-75 -------------------------------------------------------------------

def test_list_word_sets(client, db_session):
    _, headers = _user(db_session, "ws.a1@example.com", role="admin")
    owner, _ = _user(db_session, "ws.a2@example.com")
    _word_set(db_session, owner.id, "Công khai", n_items=3)
    _word_set(db_session, owner.id, "Riêng tư", is_public=False)

    body = client.get("/api/v1/admin/word-sets", headers=headers).json()
    assert body["total"] == 2
    public_row = next(r for r in body["items"] if r["name"] == "Công khai")
    assert public_row["item_count"] == 3 and public_row["owner_name"] == "ws.a"

    only_public = client.get("/api/v1/admin/word-sets?is_public=true", headers=headers).json()
    assert only_public["total"] == 1


def test_toggle_featured_closes_uc22(client, db_session):
    """UC-75 -> UC-22: Admin gắn nổi bật thì bộ xuất hiện ở khu vực Nổi bật."""
    _, admin_headers = _user(db_session, "ws.b1@example.com", role="admin")
    owner, _ = _user(db_session, "ws.b2@example.com")
    _, learner_headers = _user(db_session, "ws.b3@example.com")
    ws = _word_set(db_session, owner.id, "Bộ hay")

    assert client.get("/api/v1/discover/featured", headers=learner_headers).json() == []

    r = client.patch(f"/api/v1/admin/word-sets/{ws.id}",
                     json={"is_featured": True}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["is_featured"] is True

    featured = client.get("/api/v1/discover/featured", headers=learner_headers).json()
    assert [c["name"] for c in featured] == ["Bộ hay"]

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "word_set.update")
    ).scalars().one()
    assert "is_featured=True" in entry.detail


def test_admin_unpublish_word_set(client, db_session):
    _, admin_headers = _user(db_session, "ws.c1@example.com", role="admin")
    owner, _ = _user(db_session, "ws.c2@example.com")
    _, learner_headers = _user(db_session, "ws.c3@example.com")
    ws = _word_set(db_session, owner.id, "Bộ vi phạm")

    client.patch(f"/api/v1/admin/word-sets/{ws.id}", json={"is_public": False}, headers=admin_headers)
    assert client.get(f"/api/v1/discover/{ws.id}", headers=learner_headers).status_code == 404


def test_admin_soft_delete_word_set(client, db_session):
    """UC-75 E1 / Q6 — xóa mềm: biến khỏi kho nhưng bản ghi vẫn còn."""
    _, admin_headers = _user(db_session, "ws.d1@example.com", role="admin")
    owner, _ = _user(db_session, "ws.d2@example.com")
    ws = _word_set(db_session, owner.id, "Bộ xóa")

    assert client.delete(f"/api/v1/admin/word-sets/{ws.id}", headers=admin_headers).status_code == 204
    assert client.get("/api/v1/admin/word-sets", headers=admin_headers).json()["total"] == 0

    db_session.refresh(ws)
    assert ws.deleted_at is not None

    assert client.delete(f"/api/v1/admin/word-sets/{ws.id}", headers=admin_headers).status_code == 404


def test_word_set_admin_requires_admin(client, db_session):
    owner, learner_headers = _user(db_session, "ws.e@example.com")
    ws = _word_set(db_session, owner.id, "Bộ")
    assert client.get("/api/v1/admin/word-sets", headers=learner_headers).status_code == 403
    assert client.patch(f"/api/v1/admin/word-sets/{ws.id}",
                        json={"is_featured": True}, headers=learner_headers).status_code == 403
