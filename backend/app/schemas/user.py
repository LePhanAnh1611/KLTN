from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.achievement import AchievementStatus


class UserUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)


class AvatarResponse(BaseModel):
    avatar_url: str


class PublicProfile(BaseModel):
    """UC-55 — hồ sơ công khai. Khi `is_private` (UC-09 profile_visibility='private')
    các chỉ số bị ẩn: chỉ còn tên + avatar."""

    user_id: int
    display_name: str
    avatar_url: str | None
    bio: str | None = None
    joined_at: datetime | None = None
    is_private: bool = False
    is_me: bool = False

    level: int | None = None
    level_title: str | None = None
    xp: int | None = None
    streak_count: int | None = None
    items_mastered: int | None = None
    achievements: list[AchievementStatus] = []
