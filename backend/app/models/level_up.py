from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LevelUpSuggestion(Base, TimestampMixin):
    """UC-85 — một lần hệ thống đề xuất người học nâng trình độ CEFR.

    Lưu thành bảng riêng thay vì một cờ trong USER_SETTINGS vì cần ba thứ:
    (1) biết người học đã TỪ CHỐI cặp mức nào để không đề xuất lại,
    (2) giữ bằng chứng tại thời điểm đề xuất (mastery trung bình, số từ đã xét)
        — đề xuất phải giải thích được, không phải "hệ thống bảo thế",
    (3) có lịch sử nâng trình độ để đối chiếu với đường tiến bộ trong khóa luận.
    """

    __tablename__ = "level_up_suggestions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    from_level: Mapped[str] = mapped_column(String(5), nullable=False)
    to_level: Mapped[str] = mapped_column(String(5), nullable=False)
    # pending -> người học chưa quyết định; accepted -> đã nâng; declined -> giữ mức cũ
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", index=True
    )
    # Bằng chứng tại thời điểm đề xuất (BR-LU-02)
    avg_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    items_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
