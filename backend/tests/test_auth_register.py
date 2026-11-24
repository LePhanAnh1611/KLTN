from sqlalchemy import select

from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings

VALID_PAYLOAD = {
    "email": "hoc.vien@example.com",
    "password": "Abcd1234",
    "password_confirm": "Abcd1234",
    "display_name": "Hoc Vien",
}


def test_register_success(client, db_session):
    response = client.post("/api/v1/auth/register", json=VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == VALID_PAYLOAD["email"]
    assert body["display_name"] == VALID_PAYLOAD["display_name"]
    assert body["role"] == "learner"
    assert "password" not in body
    assert "password_hash" not in body

    user = db_session.execute(
        select(User).where(User.email == VALID_PAYLOAD["email"])
    ).scalar_one()
    assert user.password_hash != VALID_PAYLOAD["password"]
    assert user.role == "learner"
    assert user.is_active is True

    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one()
    assert progress.xp == 0
    assert progress.streak_count == 0
    assert progress.items_mastered == 0

    user_settings = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    assert user_settings.dark_mode is False
    assert user_settings.ui_language == "vi"
    assert user_settings.profile_visibility == "public"


def test_register_invalid_email(client):
    payload = {**VALID_PAYLOAD, "email": "not-an-email"}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_password_mismatch(client):
    payload = {**VALID_PAYLOAD, "password_confirm": "Different123"}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_weak_password_too_short(client):
    payload = {**VALID_PAYLOAD, "password": "Ab1", "password_confirm": "Ab1"}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_weak_password_no_digit(client):
    payload = {**VALID_PAYLOAD, "password": "Abcdefgh", "password_confirm": "Abcdefgh"}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_missing_display_name(client):
    payload = {**VALID_PAYLOAD, "display_name": ""}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_duplicate_email(client, db_session):
    first = client.post("/api/v1/auth/register", json=VALID_PAYLOAD)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=VALID_PAYLOAD)

    assert second.status_code == 409
    assert "Email" in second.json()["detail"]

    count = db_session.execute(
        select(User).where(User.email == VALID_PAYLOAD["email"])
    ).scalars().all()
    assert len(count) == 1
