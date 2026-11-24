from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WordSetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    difficulty: str | None = Field(default=None, max_length=20)
    #: Mức CEFR của bộ (A1…C2). Bộ tự tạo để trống được.
    cefr_level: str | None = Field(default=None, max_length=10)
    cover_image_url: str | None = Field(default=None, max_length=500)
    #: UC-96 — nhãn lọc chéo. Không validate ở đây: `tag_service.clean_tags`
    #: chuẩn hóa và cắt theo trần, nên "IELTS Writing" vẫn nhận được và thành
    #: 'ielts-writing' thay vì bị 422 vì có dấu cách.
    tags: list[str] | None = None


class WordSetUpdateRequest(WordSetCreateRequest):
    pass


class WordSetResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str | None
    category: str | None
    difficulty: str | None
    cover_image_url: str | None
    is_public: bool
    is_featured: bool
    download_count: int
    item_count: int = 0       # không có trên ORM; gán trong service qua _to_response
    mastered_count: int = 0   # UC-16: số từ đã thuộc (mastery >= 0.9, BR-01)
    learning_count: int = 0   # đã học >= 1 lần nhưng chưa thuộc (thanh tiến độ 3 nấc)
    tags: list[str] = []      # UC-96
    created_at: datetime


class PublishRequest(BaseModel):
    is_public: bool
