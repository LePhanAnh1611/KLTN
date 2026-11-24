"""UC-19/20/21 — Khám phá & tải bộ từ công khai."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SortOption = Literal["popular", "new", "rating"]


class ItemPreview(BaseModel):
    model_config = {"from_attributes": True}

    word: str
    meaning: str
    phonetic: str | None = None
    part_of_speech: str | None = None


class PublicWordSetCard(BaseModel):
    """Thẻ bộ từ công khai trong lưới Khám phá (UC-19)."""
    id: int
    name: str
    description: str | None
    category: str | None
    difficulty: str | None
    cover_image_url: str | None
    download_count: int
    is_featured: bool
    owner_name: str
    item_count: int
    is_downloaded: bool  # user đã tải bộ này chưa (đã có bản sao trong thư viện)
    rating_avg: float | None = None  # UC-23
    rating_count: int = 0
    tags: list[str] = []             # UC-96


class TagCount(BaseModel):
    """UC-96 — nhãn kèm số bộ công khai đang mang nó."""
    tag: str
    count: int


class PublicListResponse(BaseModel):
    """UC-19: kết quả có phân trang."""
    items: list[PublicWordSetCard]
    total: int
    page: int
    page_size: int


class PublicWordSetDetail(PublicWordSetCard):
    """UC-20: chi tiết + preview một số từ."""
    created_at: datetime
    preview_items: list[ItemPreview]
