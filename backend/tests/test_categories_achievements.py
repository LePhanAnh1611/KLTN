"""UC-76 quản lý danh mục · UC-79 CRUD định nghĩa huy hiệu (Admin)."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.item import Item
from app.models.user_achievement import UserAchievement
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import achievement_service
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


def _word_set(db_session, owner_id, name, category):
    ws = WordSet(owner_id=owner_id, name=name, category=category, difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    db_session.add(Item(word_set_id=ws.id, word="w", meaning="m"))
    db_session.commit()
    db_session.refresh(ws)
    return ws


# --- UC-76 -------------------------------------------------------------------

def test_create_and_list_categories(client, db_session):
    _, admin_headers = _user(db_session, "ct.a1@example.com", role="admin")
    _, learner_headers = _user(db_session, "ct.a2@example.com")

    r = client.post("/api/v1/admin/categories", headers=admin_headers,
                    json={"name": "Kinh doanh", "description": "Từ vựng thương mại"})
    assert r.status_code == 201 and r.json()["is_active"] is True

    client.post("/api/v1/admin/categories", headers=admin_headers,
                json={"name": "Ẩn", "is_active": False})

    admin_view = client.get("/api/v1/admin/categories", headers=admin_headers).json()
    assert {c["name"] for c in admin_view} == {"Kinh doanh", "Ẩn"}   # admin thấy cả mục tắt

    learner_view = client.get("/api/v1/discover/categories", headers=learner_headers).json()
    assert [c["name"] for c in learner_view] == ["Kinh doanh"]       # người học chỉ thấy mục bật


def test_duplicate_category_name_rejected(client, db_session):
    _, headers = _user(db_session, "ct.b@example.com", role="admin")
    client.post("/api/v1/admin/categories", headers=headers, json={"name": "Science"})
    assert client.post("/api/v1/admin/categories", headers=headers,
                       json={"name": "Science"}).status_code == 409


def test_rename_category_syncs_word_sets(client, db_session):
    """Đổi tên danh mục thì bộ từ đang gắn cũng đổi theo (bộ lọc UC-19 không lệch)."""
    _, admin_headers = _user(db_session, "ct.c1@example.com", role="admin")
    owner, _ = _user(db_session, "ct.c2@example.com")
    category = client.post("/api/v1/admin/categories", headers=admin_headers,
                           json={"name": "Culture"}).json()
    ws = _word_set(db_session, owner.id, "Bộ văn hóa", "Culture")

    r = client.patch(f"/api/v1/admin/categories/{category['id']}",
                     json={"name": "Văn hóa"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["name"] == "Văn hóa"

    db_session.refresh(ws)
    assert ws.category == "Văn hóa"

    rows = client.get("/api/v1/admin/categories", headers=admin_headers).json()
    assert rows[0]["word_set_count"] == 1


def test_delete_category_in_use_blocked(client, db_session):
    """UC-76 E1 — còn bộ từ đang gắn thì không cho xóa."""
    _, admin_headers = _user(db_session, "ct.d1@example.com", role="admin")
    owner, _ = _user(db_session, "ct.d2@example.com")
    category = client.post("/api/v1/admin/categories", headers=admin_headers,
                           json={"name": "Travel"}).json()
    ws = _word_set(db_session, owner.id, "Bộ du lịch", "Travel")

    r = client.delete(f"/api/v1/admin/categories/{category['id']}", headers=admin_headers)
    assert r.status_code == 409 and "1 bộ từ" in r.json()["detail"]

    ws.category = None
    db_session.commit()
    assert client.delete(f"/api/v1/admin/categories/{category['id']}",
                         headers=admin_headers).status_code == 204


def test_category_admin_writes_audit(client, db_session):
    _, headers = _user(db_session, "ct.e@example.com", role="admin")
    client.post("/api/v1/admin/categories", headers=headers, json={"name": "Tech"})

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "category.create")
    ).scalars().one()
    assert entry.detail == "Tech"


def test_category_admin_requires_admin(client, db_session):
    _, learner = _user(db_session, "ct.f@example.com")
    assert client.get("/api/v1/admin/categories", headers=learner).status_code == 403
    assert client.post("/api/v1/admin/categories", headers=learner,
                       json={"name": "X"}).status_code == 403


# --- UC-79 -------------------------------------------------------------------

def test_default_achievements_seeded(client, db_session):
    _, headers = _user(db_session, "ac.a@example.com", role="admin")
    rows = client.get("/api/v1/admin/achievements", headers=headers).json()
    assert len(rows) == len(achievement_service.DEFAULT_ACHIEVEMENTS)
    assert rows[0]["code"] == "first_session" and rows[0]["condition_key"] == "sessions_completed"


def test_create_custom_achievement_and_unlock(client, db_session):
    """Huy hiệu Admin thêm mới được cấp đúng như huy hiệu mặc định (UC-48)."""
    _, admin_headers = _user(db_session, "ac.b1@example.com", role="admin")
    learner, learner_headers = _user(db_session, "ac.b2@example.com")

    r = client.post("/api/v1/admin/achievements", headers=admin_headers, json={
        "code": "streak_2", "name": "Khởi động", "description": "Streak 2 ngày",
        "condition_key": "streak", "threshold": 2, "sort_order": 10,
    })
    assert r.status_code == 201

    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == learner.id)
    ).scalar_one()
    progress.streak_count = 2
    db_session.commit()

    names = achievement_service.check_and_unlock(db_session, learner)
    assert "Khởi động" in names

    codes = {a["code"] for a in
             client.get("/api/v1/achievements", headers=learner_headers).json() if a["unlocked"]}
    assert "streak_2" in codes


def test_duplicate_code_and_bad_condition_rejected(client, db_session):
    _, headers = _user(db_session, "ac.c@example.com", role="admin")
    base = {"name": "X", "description": "Y", "condition_key": "xp", "threshold": 5}

    assert client.post("/api/v1/admin/achievements", headers=headers,
                       json={**base, "code": "xp_100"}).status_code == 409
    assert client.post("/api/v1/admin/achievements", headers=headers,
                       json={**base, "code": "moi", "condition_key": "khong_ton_tai"}).status_code == 400
    assert client.post("/api/v1/admin/achievements", headers=headers,
                       json={**base, "code": "CHU HOA"}).status_code == 422


def test_update_threshold_changes_unlock_rule(client, db_session):
    """Sửa ngưỡng huy hiệu thì luật cấp đổi theo ngay."""
    _, admin_headers = _user(db_session, "ac.d1@example.com", role="admin")
    learner, _ = _user(db_session, "ac.d2@example.com")

    rows = client.get("/api/v1/admin/achievements", headers=admin_headers).json()
    xp_100 = next(a for a in rows if a["code"] == "xp_100")
    client.patch(f"/api/v1/admin/achievements/{xp_100['id']}",
                 json={"threshold": 20}, headers=admin_headers)

    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == learner.id)
    ).scalar_one()
    progress.xp = 30
    db_session.commit()

    names = achievement_service.check_and_unlock(db_session, learner)
    assert "Tân binh" in names   # 30 XP giờ đã đủ (ngưỡng 20)


def test_deactivate_hides_from_learner(client, db_session):
    _, admin_headers = _user(db_session, "ac.e1@example.com", role="admin")
    _, learner_headers = _user(db_session, "ac.e2@example.com")

    rows = client.get("/api/v1/admin/achievements", headers=admin_headers).json()
    target = rows[0]
    client.patch(f"/api/v1/admin/achievements/{target['id']}",
                 json={"is_active": False}, headers=admin_headers)

    codes = {a["code"] for a in client.get("/api/v1/achievements", headers=learner_headers).json()}
    assert target["code"] not in codes
    # định nghĩa vẫn còn ở màn quản trị
    assert any(a["code"] == target["code"] for a in
               client.get("/api/v1/admin/achievements", headers=admin_headers).json())


def test_delete_definition_keeps_granted_history(client, db_session):
    """Xóa định nghĩa không xóa huy hiệu đã cấp cho người dùng."""
    _, admin_headers = _user(db_session, "ac.f1@example.com", role="admin")
    learner, _ = _user(db_session, "ac.f2@example.com")
    db_session.add(UserAchievement(user_id=learner.id, achievement_code="xp_100"))
    db_session.commit()

    rows = client.get("/api/v1/admin/achievements", headers=admin_headers).json()
    xp_100 = next(a for a in rows if a["code"] == "xp_100")
    assert client.delete(f"/api/v1/admin/achievements/{xp_100['id']}",
                         headers=admin_headers).status_code == 204

    kept = db_session.execute(
        select(UserAchievement).where(UserAchievement.user_id == learner.id)
    ).scalars().all()
    assert len(kept) == 1 and kept[0].achievement_code == "xp_100"


def test_achievement_admin_requires_admin(client, db_session):
    _, learner = _user(db_session, "ac.g@example.com")
    assert client.get("/api/v1/admin/achievements", headers=learner).status_code == 403
