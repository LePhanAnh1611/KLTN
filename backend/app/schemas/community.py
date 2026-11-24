"""UC-49..UC-53 — feed cộng đồng (bài viết, bình luận, thích)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PostType = Literal["tip", "word", "question", "resource", "word_set", "progress", "share"]


class PostCreate(BaseModel):
    post_type: PostType = "tip"
    content: str = Field(min_length=1, max_length=2000)
    image_url: str | None = Field(default=None, max_length=500)


class PostCard(BaseModel):
    id: int
    post_type: str
    content: str
    image_url: str | None
    status: str
    created_at: datetime
    author_id: int
    author_name: str
    author_avatar_url: str | None
    like_count: int
    comment_count: int
    liked_by_me: bool
    is_mine: bool


class PostListResponse(BaseModel):
    items: list[PostCard]
    total: int
    page: int
    page_size: int


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    id: int
    post_id: int
    content: str
    created_at: datetime
    author_id: int
    author_name: str
    is_mine: bool


class ReactionResponse(BaseModel):
    """UC-51 — trạng thái sau khi bấm thích/bỏ thích."""

    post_id: int
    like_count: int
    liked_by_me: bool


LeaderboardScope = Literal["all", "week"]


class LeaderboardRow(BaseModel):
    """UC-54 — một dòng bảng xếp hạng."""

    rank: int
    user_id: int
    display_name: str
    avatar_url: str | None
    xp: int           # XP theo phạm vi đang xem (toàn thời gian hoặc tuần)
    level: int        # level luôn tính từ XP tích lũy
    level_title: str
    #: Chuỗi ngày học liên tiếp — LUÔN là giá trị hiện tại, không đổi theo
    #: `scope`. Xếp hạng theo XP tuần mà hiện streak "của tuần" thì phải định
    #: nghĩa streak trong một cửa sổ 7 ngày, một khái niệm không tồn tại.
    streak_count: int = 0
    is_me: bool


class LeaderboardResponse(BaseModel):
    scope: LeaderboardScope
    items: list[LeaderboardRow]
    my_rank: int | None = None
    my_row: LeaderboardRow | None = None  # chỉ có khi người xem nằm ngoài top
