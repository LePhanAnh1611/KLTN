import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user
from app.core.security import decode_access_token
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user

VALID_PAYLOAD = {
    "email": "login.user@example.com",
    "password": "Abcd1234",
    "password_confirm": "Abcd1234",
    "display_name": "Login User",
}


def _create_user(db_session):
    return register_user(db_session, RegisterRequest(**VALID_PAYLOAD))


def test_login_success(client, db_session):
    user = _create_user(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_PAYLOAD["email"], "password": VALID_PAYLOAD["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "learner"


def test_login_wrong_password(client, db_session):
    _create_user(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_PAYLOAD["email"], "password": "WrongPass1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Email hoặc mật khẩu không đúng"


def test_login_unknown_email(client, db_session):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "no-such-user@example.com", "password": "Whatever1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Email hoặc mật khẩu không đúng"


def test_login_locked_account(client, db_session):
    user = _create_user(db_session)
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_PAYLOAD["email"], "password": VALID_PAYLOAD["password"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Tài khoản đã bị khóa"


def test_get_current_user_valid_token(db_session):
    user = _create_user(db_session)
    from app.core.security import create_access_token

    token = create_access_token(user.id, user.role)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    current_user = get_current_user(credentials=credentials, db=db_session)

    assert current_user.id == user.id


def test_get_current_user_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-valid-token")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=credentials, db=db_session)

    assert exc_info.value.status_code == 401
