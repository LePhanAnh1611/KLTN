import io

from app.core.security import create_access_token
from app.schemas.auth import RegisterRequest
from app.services import user_service
from app.services.auth_service import register_user

VALID_PAYLOAD = {
    "email": "profile.user@example.com",
    "password": "Abcd1234",
    "password_confirm": "Abcd1234",
    "display_name": "Profile User",
}


def _create_user_and_token(db_session):
    user = register_user(db_session, RegisterRequest(**VALID_PAYLOAD))
    token = create_access_token(user.id, user.role)
    return user, token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_get_me_success(client, db_session):
    user, token = _create_user_and_token(db_session)

    response = client.get("/api/v1/users/me", headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == VALID_PAYLOAD["email"]
    assert body["display_name"] == VALID_PAYLOAD["display_name"]


def test_get_me_requires_auth(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401  # missing Authorization header


def test_update_me_success(client, db_session):
    user, token = _create_user_and_token(db_session)

    response = client.patch(
        "/api/v1/users/me",
        json={"display_name": "New Name", "bio": "Hello there"},
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "New Name"
    assert body["bio"] == "Hello there"

    db_session.refresh(user)
    assert user.display_name == "New Name"
    assert user.bio == "Hello there"


def test_update_me_empty_name_rejected(client, db_session):
    _, token = _create_user_and_token(db_session)

    response = client.patch(
        "/api/v1/users/me",
        json={"display_name": "", "bio": None},
        headers=_auth_header(token),
    )

    assert response.status_code == 422


def test_upload_avatar_success(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(user_service, "UPLOAD_DIR", tmp_path)
    user, token = _create_user_and_token(db_session)

    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.jpg", fake_image, "image/jpeg")},
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    avatar_url = response.json()["avatar_url"]
    assert avatar_url.startswith("/uploads/avatars/")

    saved_files = list(tmp_path.iterdir())
    assert len(saved_files) == 1

    db_session.refresh(user)
    assert user.avatar_url == avatar_url


def test_upload_avatar_invalid_type_rejected(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(user_service, "UPLOAD_DIR", tmp_path)
    user, token = _create_user_and_token(db_session)

    fake_file = io.BytesIO(b"not an image")
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("notes.txt", fake_file, "text/plain")},
        headers=_auth_header(token),
    )

    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []

    db_session.refresh(user)
    assert user.avatar_url is None


def test_upload_avatar_too_large_rejected(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(user_service, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(user_service, "MAX_AVATAR_SIZE_BYTES", 10)
    _, token = _create_user_and_token(db_session)

    fake_image = io.BytesIO(b"this is definitely more than 10 bytes")
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.jpg", fake_image, "image/jpeg")},
        headers=_auth_header(token),
    )

    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_upload_avatar_requires_auth(client):
    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    response = client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.jpg", fake_image, "image/jpeg")},
    )

    assert response.status_code == 401


# --- UC-55 hồ sơ công khai ---------------------------------------------------

def _other_user(db_session, email, xp=0, streak=0):
    """register_user đã tạo sẵn UserProgress/UserSettings — chỉ cập nhật chỉ số."""
    from sqlalchemy import select

    from app.models.user_progress import UserProgress

    user = register_user(db_session, RegisterRequest(
        email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:5],
    ))
    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one()
    progress.xp = xp
    progress.streak_count = streak
    progress.items_mastered = 3
    db_session.commit()
    return user, create_access_token(user.id, user.role)


def _set_private(db_session, user_id):
    """UC-09: đặt hồ sơ về riêng tư (bản ghi UserSettings tạo sẵn khi đăng ký)."""
    from sqlalchemy import select

    from app.models.user_settings import UserSettings

    settings = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one()
    settings.profile_visibility = "private"
    db_session.commit()


def test_public_profile_shows_stats(client, db_session):
    target, _ = _other_user(db_session, "pub.a@example.com", xp=250, streak=4)
    _, viewer_token = _other_user(db_session, "pub.b@example.com")

    body = client.get(f"/api/v1/users/{target.id}/public",
                      headers=_auth_header(viewer_token)).json()

    assert body["display_name"] == "pub.a" and body["is_me"] is False
    assert body["is_private"] is False
    assert body["xp"] == 250 and body["streak_count"] == 4 and body["items_mastered"] == 0
    assert body["level"] == 3 and body["level_title"] == "Học viên"
    assert body["joined_at"] is not None


def test_public_profile_private_hides_stats(client, db_session):
    """E1: hồ sơ riêng tư -> ẩn chỉ số, chỉ còn tên + avatar."""
    target, _ = _other_user(db_session, "pub.c@example.com", xp=500)
    _set_private(db_session, target.id)
    _, viewer_token = _other_user(db_session, "pub.d@example.com")

    body = client.get(f"/api/v1/users/{target.id}/public",
                      headers=_auth_header(viewer_token)).json()

    assert body["is_private"] is True
    assert body["display_name"] == "pub.c"
    assert body["xp"] is None and body["streak_count"] is None
    assert body["achievements"] == []


def test_own_private_profile_still_visible_to_self(client, db_session):
    me, token = _other_user(db_session, "pub.e@example.com", xp=120)
    _set_private(db_session, me.id)

    body = client.get(f"/api/v1/users/{me.id}/public", headers=_auth_header(token)).json()
    assert body["is_me"] is True and body["is_private"] is False and body["xp"] == 120


def test_public_profile_not_found(client, db_session):
    _, token = _other_user(db_session, "pub.f@example.com")
    assert client.get("/api/v1/users/999999/public",
                      headers=_auth_header(token)).status_code == 404
