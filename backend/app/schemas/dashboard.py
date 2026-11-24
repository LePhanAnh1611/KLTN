from __future__ import annotations

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    xp: int
    level: int
    xp_into_level: int  # XP đã tích trong level hiện tại
    xp_for_next_level: int  # XP cần để hoàn thành level hiện tại
    streak_count: int
    items_mastered: int
    word_set_count: int
    review_due_count: int
    daily_item_goal: int | None
