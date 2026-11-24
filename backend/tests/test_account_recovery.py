"""UC-03 xác thực email · UC-06 quên/đặt lại mật khẩu · UC-04 E3."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.auth_token import PURPOSE_EMAIL_VERIFY, PURPOSE_PASSWORD_RESET, AuthToken
from app.models.email_queue import EmailQueue
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services import config_service, token_service
from app.services.auth_service import register_user

PASSWORD = "Abcd1234"


def _register(client, email):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD,
        "password_confirm": PASSWORD, "display_name": email[:4],
    })


def _login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _token_from_email(db_session, email_address: str, marker: str) -> str:
    """Lấy token trong liên kết của email đã xếp hàng đợi."""
    row = db_session.execute(
        select(EmailQueue)
        .where(EmailQueue.to_email == email_address, EmailQueue.template == marker)
        .order_by(EmailQueue.id.desc())
    ).scalars().first()
    assert row is not None, f"khong tim thay email {marker}"
    line = next(ln for ln in row.body.splitlines() if "token=" in ln)
    return line.split("token=", 1)[1].strip()


# --- UC-03 -------------------------------------------------------------------

def test_register_queues_verification_email(client, db_session):
    r = _register(client, "ac.a@example.com")
    assert r.status_code == 201
    assert r.json()["is_email_verified"] is False

    row = db_session.execute(
        select(EmailQueue).where(EmailQueue.template == "email_verify")
    ).scalars().one()
    assert row.to_email == "ac.a@example.com"
    assert "verify-email?token=" in row.body


def test_verify_email_flow(client, db_session):
    _register(client, "ac.b@example.com")
    token = _token_from_email(db_session, "ac.b@example.com", "email_verify")

    r = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    assert r.json() == {"email": "ac.b@example.com", "already_verified": False}

    user = db_session.execute(
        select(User).where(User.email == "ac.b@example.com")
    ).scalar_one()
    assert user.is_email_verified is True


def test_token_is_single_use(client, db_session):
    """Quy tắc: một token dùng một lần."""
    _register(client, "ac.c@example.com")
    token = _token_from_email(db_session, "ac.c@example.com", "email_verify")

    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_invalid_and_expired_token(client, db_session):
    """E1 — token sai hoặc hết hạn."""
    _register(client, "ac.d@example.com")
    assert client.post("/api/v1/auth/verify-email",
                       json={"token": "khong-ton-tai"}).status_code == 400

    row = db_session.execute(select(AuthToken)).scalars().one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    token = _token_from_email(db_session, "ac.d@example.com", "email_verify")
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_resend_verification_and_limit(client, db_session):
    """Luồng 1a — gửi lại được, nhưng có giới hạn số lần."""
    _register(client, "ac.e@example.com")
    token_login = _login(client, "ac.e@example.com").json()["access_token"]
    headers = {"Authorization": f"Bearer {token_login}"}

    # đăng ký đã tiêu 1 lượt -> còn 2 lượt trong cửa sổ
    assert client.post("/api/v1/auth/resend-verification", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/resend-verification", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/resend-verification", headers=headers).status_code == 429


def test_resend_when_already_verified(client, db_session):
    """E2 — email đã xác thực trước đó."""
    _register(client, "ac.f@example.com")
    token = _token_from_email(db_session, "ac.f@example.com", "email_verify")
    client.post("/api/v1/auth/verify-email", json={"token": token})

    headers = {"Authorization": f"Bearer {_login(client, 'ac.f@example.com').json()['access_token']}"}
    assert client.post("/api/v1/auth/resend-verification", headers=headers).status_code == 409


def test_only_latest_verification_link_works(client, db_session):
    """Gửi lại thì liên kết cũ hết hiệu lực."""
    _register(client, "ac.g@example.com")
    old_token = _token_from_email(db_session, "ac.g@example.com", "email_verify")

    headers = {"Authorization": f"Bearer {_login(client, 'ac.g@example.com').json()['access_token']}"}
    client.post("/api/v1/auth/resend-verification", headers=headers)
    new_token = _token_from_email(db_session, "ac.g@example.com", "email_verify")
    assert new_token != old_token

    assert client.post("/api/v1/auth/verify-email", json={"token": old_token}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": new_token}).status_code == 200


# --- UC-04 E3 ----------------------------------------------------------------

def test_login_allowed_when_verification_not_required(client, db_session):
    """Mặc định KHÔNG bắt buộc xác thực -> đăng nhập được, kèm cờ để FE nhắc."""
    _register(client, "ac.h@example.com")
    body = _login(client, "ac.h@example.com").json()
    assert body["email_verified"] is False and body["access_token"]


def test_login_blocked_when_verification_required(client, db_session):
    """E3 — Admin bật bắt buộc xác thực (UC-81) thì chưa xác thực không vào được."""
    _register(client, "ac.i@example.com")
    config_service.set_values(db_session, {"require_email_verification": True})

    assert _login(client, "ac.i@example.com").status_code == 403

    token = _token_from_email(db_session, "ac.i@example.com", "email_verify")
    client.post("/api/v1/auth/verify-email", json={"token": token})
    assert _login(client, "ac.i@example.com").status_code == 200


# --- UC-06 -------------------------------------------------------------------

def test_forgot_password_flow(client, db_session):
    _register(client, "ac.j@example.com")

    r = client.post("/api/v1/auth/forgot-password", json={"email": "ac.j@example.com"})
    assert r.status_code == 200
    token = _token_from_email(db_session, "ac.j@example.com", "password_reset")

    new_password = "Moi98765"
    assert client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": new_password, "new_password_confirm": new_password,
    }).status_code == 204

    assert _login(client, "ac.j@example.com", PASSWORD).status_code == 401
    assert _login(client, "ac.j@example.com", new_password).status_code == 200


def test_forgot_password_unknown_email_is_silent(client, db_session):
    """Luồng 1a — không tiết lộ email có tồn tại hay không."""
    known = client.post("/api/v1/auth/forgot-password", json={"email": "ac.k@example.com"})
    _register(client, "ac.k@example.com")
    after = client.post("/api/v1/auth/forgot-password", json={"email": "ac.k@example.com"})

    assert known.status_code == after.status_code == 200
    assert known.json() == after.json()          # cùng một câu trả lời

    # email chưa tồn tại thì không sinh gì trong hàng đợi
    reset_emails = db_session.execute(
        select(EmailQueue).where(EmailQueue.template == "password_reset")
    ).scalars().all()
    assert len(reset_emails) == 1


def test_reset_token_single_use_and_expiry(client, db_session):
    _register(client, "ac.l@example.com")
    client.post("/api/v1/auth/forgot-password", json={"email": "ac.l@example.com"})
    token = _token_from_email(db_session, "ac.l@example.com", "password_reset")
    body = {"token": token, "new_password": "Moi98765", "new_password_confirm": "Moi98765"}

    assert client.post("/api/v1/auth/reset-password", json=body).status_code == 204
    assert client.post("/api/v1/auth/reset-password", json=body).status_code == 400   # dùng lại


def test_reset_password_expired_token(client, db_session):
    """E1 — token hết hạn."""
    _register(client, "ac.m@example.com")
    client.post("/api/v1/auth/forgot-password", json={"email": "ac.m@example.com"})
    token = _token_from_email(db_session, "ac.m@example.com", "password_reset")

    row = db_session.execute(
        select(AuthToken).where(AuthToken.purpose == PURPOSE_PASSWORD_RESET)
    ).scalars().one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    assert client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "Moi98765", "new_password_confirm": "Moi98765",
    }).status_code == 400


def test_reset_password_weak_rejected(client, db_session):
    """E2 — mật khẩu mới không đạt yêu cầu."""
    _register(client, "ac.n@example.com")
    client.post("/api/v1/auth/forgot-password", json={"email": "ac.n@example.com"})
    token = _token_from_email(db_session, "ac.n@example.com", "password_reset")

    assert client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "short1", "new_password_confirm": "short1",
    }).status_code == 422
    assert client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "khongcoso", "new_password_confirm": "khongcoso",
    }).status_code == 422


def test_token_stored_hashed_not_raw(client, db_session):
    """Bảo mật: DB không giữ token gốc."""
    _register(client, "ac.o@example.com")
    token = _token_from_email(db_session, "ac.o@example.com", "email_verify")

    row = db_session.execute(
        select(AuthToken).where(AuthToken.purpose == PURPOSE_EMAIL_VERIFY)
    ).scalars().one()
    assert row.token_hash != token
    assert row.token_hash == token_service.hash_token(token)


def test_locked_account_gets_no_reset_email(client, db_session):
    user = register_user(db_session, RegisterRequest(
        email="ac.p@example.com", password=PASSWORD,
        password_confirm=PASSWORD, display_name="acp",
    ))
    user.is_active = False
    db_session.commit()

    client.post("/api/v1/auth/forgot-password", json={"email": "ac.p@example.com"})
    assert db_session.execute(
        select(EmailQueue).where(EmailQueue.template == "password_reset")
    ).scalars().all() == []
