from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserProgress(TimestampMixin, Base):
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    streak_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    items_mastered: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_activity_date: Mapped[date | None] = mapped_column(Date)
