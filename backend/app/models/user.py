from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="learner", server_default="learner")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # UC-03: đã bấm liên kết xác thực trong email chưa
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # UC-12: xóa mềm theo Q6 — INTERACTION của người này là dữ liệu huấn luyện
    # DKT, xóa cứng sẽ phá vỡ lịch sử. Email được thay bằng chuỗi ẩn danh để
    # giải phóng địa chỉ cho lần đăng ký sau.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: UC-84 — phiên bản lộ trình người này thấy (xem LearningStage.roadmap_version).
    #: Tài khoản có từ trước migration giữ 1 (pilot học tiếp đúng bản đồ cũ);
    #: tài khoản mới mặc định 2.
    roadmap_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default="2"
    )
