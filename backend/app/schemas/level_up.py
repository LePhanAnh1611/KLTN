from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LevelUpSuggestionOut(BaseModel):
    """UC-85 — một đề xuất nâng trình độ đang chờ người học quyết định."""

    model_config = {"from_attributes": True}

    id: int
    from_level: str
    to_level: str
    status: str
    avg_mastery: float
    items_considered: int
    created_at: datetime


class LevelUpStatus(BaseModel):
    """Bảng điều kiện nâng trình độ — luôn trả đủ số liệu để giải thích cho người học
    VÌ SAO chưa đủ điều kiện, thay vì chỉ trả về true/false."""

    current_level: str
    next_level: str | None            # None = đã ở mức cao nhất (C2)
    eligible: bool

    # Bằng chứng (BR-LU-01, BR-LU-02)
    stages_total: int                 # số chặng thuộc mức hiện tại
    stages_mastered: int
    avg_mastery: float
    items_considered: int

    # Ngưỡng đang áp dụng, để giao diện hiển thị "x/y" mà không hardcode
    required_avg_mastery: float
    required_items: int

    suggestion: LevelUpSuggestionOut | None = None
