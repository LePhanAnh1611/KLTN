from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ReviewItem(BaseModel):
    item_id: int
    word: str
    meaning: str
    word_set_id: int
    word_set_name: str
    next_review_at: datetime
    interval_days: int
    scheduled_for: date | None = None
    mastery: float | None = None
    at_risk: bool = False


class WeakReviewItem(BaseModel):
    """UC-86 — từ có mastery thấp, KHÔNG phụ thuộc lịch ôn.

    Khác `ReviewItem`: item ở đây có thể chưa từng được xếp lịch (VD trả lời sai
    ngay lần đầu), nên không có `next_review_at`/`interval_days`.
    """

    item_id: int
    word: str
    meaning: str
    word_set_id: int
    word_set_name: str
    mastery: float


class ReviewCalendar(BaseModel):
    today: list[ReviewItem]      # đến hạn hôm nay hoặc quá hạn
    tomorrow: list[ReviewItem]
    this_week: list[ReviewItem]  # trong 2..7 ngày tới
    daily_limit: int = 30
    reviewed_today: int = 0
    backlog_count: int = 0
    estimated_minutes: int = 0
    lower_level_count: int = 0
    entry_level: str = "A1"


class ReviewCleanupResult(BaseModel):
    paused_count: int
