from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

PURPOSE_EMAIL_VERIFY = "email_verify"    # UC-03
PURPOSE_PASSWORD_RESET = "password_reset"  # UC-06


class AuthToken(Base, TimestampMixin):
    """Token dùng một lần, có hạn — cho UC-03 (xác thực email) và UC-06 (đặt lại
    mật khẩu).

    Lưu HASH của token chứ không lưu token gốc: nếu DB bị lộ thì kẻ tấn công vẫn
    không dựng lại được liên kết trong email. `used_at` đảm bảo mỗi token chỉ
    dùng một lần.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
