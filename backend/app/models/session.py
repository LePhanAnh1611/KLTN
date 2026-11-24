from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudySession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    word_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("word_sets.id"), index=True
    )
    mode: Mapped[str | None] = mapped_column(String(30))
    # UC-35: phiên "luyện thường" — vẫn ghi Interaction & cập nhật mastery,
    # nhưng KHÔNG đụng tới REVIEW_SCHEDULE (xem session_service.record_answer).
    practice_only: Mapped[bool] = mapped_column(default=False, server_default="false")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="in_progress", server_default="in_progress"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    item_count: Mapped[int | None] = mapped_column(Integer)
    correct_count: Mapped[int | None] = mapped_column(Integer)
    xp_earned: Mapped[int | None] = mapped_column(Integer)
    completion_summary: Mapped[dict | None] = mapped_column(JSON)
