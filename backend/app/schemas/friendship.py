"""UC-56 kết bạn · UC-57 chia sẻ tiến độ."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 'self' = đang xem hồ sơ của chính mình, 'none' = chưa có quan hệ
FriendStatus = Literal["self", "none", "pending", "accepted"]


class FriendshipState(BaseModel):
    status: FriendStatus
    friendship_id: int | None
    # true = lời mời ĐANG CHỜ TÔI trả lời (khác với lời mời tôi đã gửi đi)
    is_incoming: bool


class FriendRow(BaseModel):
    user_id: int
    display_name: str
    avatar_url: str | None
    level: int
    level_title: str
    xp: int
    streak_count: int


class FriendRequestRow(BaseModel):
    friendship_id: int
    user_id: int
    display_name: str
    avatar_url: str | None
    created_at: datetime


class ShareProgressRequest(BaseModel):
    message: str | None = Field(default=None, max_length=500)


class UserSearchRow(BaseModel):
    """Kết quả tìm người để kết bạn (tab Bạn bè). Chỉ tên + ID + ảnh — không lộ
    XP/streak, cùng tinh thần "chỉ hiện tên tài khoản" của bảng tin."""
    user_id: int
    display_name: str
    avatar_url: str | None
    friendship: FriendshipState
