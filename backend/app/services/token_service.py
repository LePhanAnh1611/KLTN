"""Token dùng một lần có hạn cho UC-03 (xác thực email) & UC-06 (đặt lại mật khẩu).

Token gốc chỉ tồn tại trong email gửi đi; DB chỉ giữ SHA-256 của nó. Vì vậy
`issue()` trả token gốc cho caller dùng ngay, còn `consume()` tra bằng hash.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken
from app.models.user import User

TOKEN_BYTES = 32

# Hạn dùng theo mục đích — xác thực email nới rộng hơn vì người dùng hay mở muộn
TTL = {
    "email_verify": timedelta(hours=24),
    "password_reset": timedelta(hours=1),
}

# Luồng thay thế 1a UC-03: giới hạn số lần gửi lại
MAX_ISSUES_PER_WINDOW = 3
ISSUE_WINDOW = timedelta(hours=1)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def recent_issue_count(db: Session, user: User, purpose: str) -> int:
    since = datetime.now(timezone.utc) - ISSUE_WINDOW
    return db.execute(
        select(func.count()).select_from(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.created_at >= since,
        )
    ).scalar_one()


def issue(db: Session, user: User, purpose: str, *, commit: bool = True) -> str:
    """Sinh token mới, vô hiệu các token cùng mục đích chưa dùng. Trả TOKEN GỐC."""
    now = datetime.now(timezone.utc)

    for old in db.execute(
        select(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
    ).scalars():
        old.used_at = now      # chỉ liên kết mới nhất còn hiệu lực

    raw = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(AuthToken(
        user_id=user.id, purpose=purpose, token_hash=hash_token(raw),
        expires_at=now + TTL[purpose],
    ))
    if commit:
        db.commit()
    else:
        db.flush()
    return raw


def consume(db: Session, raw: str, purpose: str) -> User | None:
    """Đổi token lấy user & đánh dấu đã dùng. None nếu sai/hết hạn/đã dùng."""
    token = db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == hash_token(raw),
            AuthToken.purpose == purpose,
        )
    ).scalar_one_or_none()

    if token is None or token.used_at is not None:
        return None

    now = datetime.now(timezone.utc)
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        return None

    token.used_at = now
    return db.get(User, token.user_id)
