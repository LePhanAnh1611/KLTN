"""UC-58/59/60/61 — thông báo in-app."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Loại thông báo — quyết định người dùng có nhận hay không (UC-60)
NotificationType = Literal[
    "review_due",     # nhắc ôn (UC-63)
    "streak_risk",    # streak sắp đứt (UC-63)
    "achievement",    # mở khóa huy hiệu (UC-48)
    "community",      # bình luận / thích bài của mình (UC-50/51)
    "level_up",       # đề xuất nâng trình độ CEFR (UC-85) — luôn nhận
    "system",         # thông báo hệ thống / broadcast (UC-82) — luôn nhận
]


class NotificationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    type: str
    title: str
    body: str | None
    link: str | None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class NotificationPreferences(BaseModel):
    """UC-60 — bật/tắt từng nhóm thông báo."""

    model_config = {"from_attributes": True}

    notify_review: bool = True
    notify_achievement: bool = True
    notify_community: bool = True
