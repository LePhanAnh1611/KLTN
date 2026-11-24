"""UC-07 đổi mật khẩu · UC-09 cài đặt · UC-10 đặt mục tiêu học."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.user_settings import UserSettings
from app.schemas.auth import RegisterRequest
from app.services.gamification_service import default_daily_item_goal
from app.services.auth_service import register_user

PASSWORD = "Abcd1234"


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password=PASSWORD, password_confirm=PASSWORD,
                        display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# --- UC-09 -------------------------------------------------------------------

def test_get_settings_returns_defaults(client, db_session):
    _, headers = _user(db_session, "st.a@example.com")

    body = client.get("/api/v1/users/me/settings", headers=headers).json()
    assert body["dark_mode"] is False
    assert body["ui_language"] == "vi"
    assert body["profile_visibility"] == "public"
    assert body["reminder_time"] is None
    assert body["daily_item_goal"] is None


def test_update_settings_partial(client, db_session):
    """Gửi field nào đổi field đó, field còn lại giữ nguyên."""
    _, headers = _user(db_session, "st.b@example.com")

    body = client.put("/api/v1/users/me/settings", headers=headers,
                      json={"dark_mode": True}).json()
    assert body["dark_mode"] is True and body["ui_language"] == "vi"

    body = client.put("/api/v1/users/me/settings", headers=headers,
                      json={"ui_language": "en", "reminder_time": "20:30:00"}).json()
    assert body["ui_language"] == "en"
    assert body["reminder_time"] == "20:30:00"
    assert body["dark_mode"] is True          # không bị ghi đè


def test_privacy_setting_hides_public_profile(client, db_session):
    """UC-09 -> UC-55: đặt hồ sơ riêng tư thì người khác không xem được chỉ số."""
    owner, owner_headers = _user(db_session, "st.c1@example.com")
    _, other_headers = _user(db_session, "st.c2@example.com")

    public = client.get(f"/api/v1/users/{owner.id}/public", headers=other_headers).json()
    assert public["is_private"] is False and public["xp"] is not None

    client.put("/api/v1/users/me/settings", headers=owner_headers,
               json={"profile_visibility": "private"})

    hidden = client.get(f"/api/v1/users/{owner.id}/public", headers=other_headers).json()
    assert hidden["is_private"] is True and hidden["xp"] is None
    assert hidden["display_name"] == owner.display_name    # tên vẫn hiện


def test_invalid_settings_values_rejected(client, db_session):
    _, headers = _user(db_session, "st.d@example.com")
    assert client.put("/api/v1/users/me/settings", headers=headers,
                      json={"ui_language": "fr"}).status_code == 422
    assert client.put("/api/v1/users/me/settings", headers=headers,
                      json={"profile_visibility": "secret"}).status_code == 422


# --- UC-10 -------------------------------------------------------------------

def test_update_goals(client, db_session):
    user, headers = _user(db_session, "st.e@example.com")

    body = client.put("/api/v1/users/me/goals", headers=headers, json={
        "daily_item_goal": 25, "daily_xp_goal": 120, "target_cefr_level": "B2",
    }).json()
    assert body["daily_item_goal"] == 25
    assert body["daily_xp_goal"] == 120
    assert body["target_cefr_level"] == "B2"

    row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    assert row.daily_item_goal == 25


def test_goals_apply_to_dashboard_and_progress(client, db_session):
    """UC-10 bước 3 — mục tiêu đã lưu phải hiện ở Trang chủ (UC-01) và Tiến độ (UC-41)."""
    _, headers = _user(db_session, "st.f@example.com")

    assert client.get("/api/v1/dashboard", headers=headers).json()["daily_item_goal"] \
        == default_daily_item_goal()                                    # luồng 1a

    client.put("/api/v1/users/me/goals", headers=headers,
               json={"daily_item_goal": 30, "daily_xp_goal": 200})

    assert client.get("/api/v1/dashboard", headers=headers).json()["daily_item_goal"] == 30
    assert client.get("/api/v1/progress", headers=headers).json()["daily_xp_goal"] == 200


def test_goals_out_of_range_rejected(client, db_session):
    """UC-10 E1 — giá trị ngoài khoảng an toàn."""
    _, headers = _user(db_session, "st.g@example.com")
    for payload in ({"daily_item_goal": 0}, {"daily_item_goal": 500},
                    {"daily_xp_goal": 5}, {"target_cefr_level": "D1"}):
        assert client.put("/api/v1/users/me/goals", headers=headers,
                          json=payload).status_code == 422


# --- UC-07 -------------------------------------------------------------------

def test_change_password_success(client, db_session):
    user, headers = _user(db_session, "st.h@example.com")
    new_password = "Xyz98765"

    r = client.post("/api/v1/users/me/password", headers=headers, json={
        "current_password": PASSWORD,
        "new_password": new_password,
        "new_password_confirm": new_password,
    })
    assert r.status_code == 204

    assert _login(client, user.email, PASSWORD).status_code == 401       # mật khẩu cũ hết dùng
    assert _login(client, user.email, new_password).status_code == 200


def test_change_password_wrong_current(client, db_session):
    """E1 — mật khẩu hiện tại sai."""
    user, headers = _user(db_session, "st.i@example.com")
    r = client.post("/api/v1/users/me/password", headers=headers, json={
        "current_password": "SaiRoi123",
        "new_password": "Xyz98765", "new_password_confirm": "Xyz98765",
    })
    assert r.status_code == 400
    assert _login(client, user.email, PASSWORD).status_code == 200       # không đổi gì


def test_change_password_same_as_old(client, db_session):
    """E2 — mật khẩu mới trùng mật khẩu cũ."""
    _, headers = _user(db_session, "st.j@example.com")
    r = client.post("/api/v1/users/me/password", headers=headers, json={
        "current_password": PASSWORD,
        "new_password": PASSWORD, "new_password_confirm": PASSWORD,
    })
    assert r.status_code == 400


def test_change_password_weak_or_mismatch(client, db_session):
    """E2 — mật khẩu mới yếu / xác nhận không khớp (cùng luật với đăng ký)."""
    _, headers = _user(db_session, "st.k@example.com")
    base = {"current_password": PASSWORD}

    assert client.post("/api/v1/users/me/password", headers=headers, json={
        **base, "new_password": "short1", "new_password_confirm": "short1",
    }).status_code == 422
    assert client.post("/api/v1/users/me/password", headers=headers, json={
        **base, "new_password": "khongcoso", "new_password_confirm": "khongcoso",
    }).status_code == 422
    assert client.post("/api/v1/users/me/password", headers=headers, json={
        **base, "new_password": "Abcd12345", "new_password_confirm": "Abcd99999",
    }).status_code == 422


def test_change_password_writes_audit(client, db_session):
    user, headers = _user(db_session, "st.l@example.com")
    client.post("/api/v1/users/me/password", headers=headers, json={
        "current_password": PASSWORD,
        "new_password": "Xyz98765", "new_password_confirm": "Xyz98765",
    })

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.password_change")
    ).scalars().one()
    assert entry.actor_id == user.id and entry.target_id == user.id


def test_settings_require_auth(client):
    assert client.get("/api/v1/users/me/settings").status_code == 401
    assert client.put("/api/v1/users/me/goals", json={}).status_code == 401
    assert client.post("/api/v1/users/me/password", json={}).status_code == 401
