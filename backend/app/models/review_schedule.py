from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, DateTime, Float, ForeignKey, Integer, Numeric, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ReviewSchedule(TimestampMixin, Base):
    __tablename__ = "review_schedules"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_review_schedule_user_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=False, index=True)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    ease_factor: Mapped[float] = mapped_column(Numeric(4, 2), default=2.5, server_default="2.5")
    repetitions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # UC-34 SM-2
    #: UC-66 bản sửa — ước lượng NỬA ĐỜI (số ngày để P(nhớ) còn một nửa) của cặp
    #: (người, từ). NULL = chưa có ước lượng; lượt ôn kế tiếp sẽ khởi tạo.
    half_life_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_paused: Mapped[bool] = mapped_column(default=False, server_default="false")
