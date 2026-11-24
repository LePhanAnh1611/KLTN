from __future__ import annotations

from datetime import time as time_

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), unique=True, nullable=False
    )
    dark_mode: Mapped[bool] = mapped_column(default=False, server_default="false")
    ui_language: Mapped[str] = mapped_column(String(10), default="vi", server_default="vi")
    reminder_time: Mapped[time_ | None] = mapped_column(Time)
    # UC-88 — tên múi giờ IANA. Quyết định "hôm nay" là ngày nào cho streak,
    # mục tiêu ngày, thử thách ngày và trần XP (xem app/core/clock.py).
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Ho_Chi_Minh", server_default="Asia/Ho_Chi_Minh"
    )
    profile_visibility: Mapped[str] = mapped_column(
        String(20), default="public", server_default="public"
    )
    daily_item_goal: Mapped[int | None] = mapped_column(Integer)
    daily_xp_goal: Mapped[int | None] = mapped_column(Integer)  # UC-41
    target_cefr_level: Mapped[str | None] = mapped_column(String(5))
    # UC-11: trình độ ĐẦU VÀO do bài kiểm tra ước lượng (khác target ở trên là
    # mục tiêu hướng tới). UC-84 dùng làm điểm xuất phát trên lộ trình (BR-RM-02).
    entry_cefr_level: Mapped[str | None] = mapped_column(String(5))

    # UC-60: bật/tắt từng loại thông báo (UC-61 E1 kiểm tra trước khi sinh)
    notify_review: Mapped[bool] = mapped_column(default=True, server_default="true")
    notify_achievement: Mapped[bool] = mapped_column(default=True, server_default="true")
    notify_community: Mapped[bool] = mapped_column(default=True, server_default="true")
