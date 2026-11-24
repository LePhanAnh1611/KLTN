"""UC-23 — đánh giá / xếp hạng bộ từ."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RatingRequest(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class RatingItem(BaseModel):
    """Một đánh giá của người khác (hiện dưới phần chi tiết bộ từ)."""

    user_name: str
    stars: int
    comment: str | None
    created_at: datetime


class RatingSummary(BaseModel):
    """Điểm trung bình + đánh giá của chính người đang xem (nếu có)."""

    average: float | None
    count: int
    my_stars: int | None = None
    my_comment: str | None = None
    can_rate: bool  # đã tải bộ từ này chưa (E1 chống spam)
    items: list[RatingItem] = []
