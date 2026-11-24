from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ItemCreateRequest(BaseModel):
    word: str = Field(min_length=1, max_length=200)
    phonetic: str | None = Field(default=None, max_length=200)
    part_of_speech: str | None = Field(default=None, max_length=50)
    meaning: str = Field(min_length=1)
    example: str | None = None


class ItemUpdateRequest(ItemCreateRequest):
    pass


class ItemProvenance(BaseModel):
    """Nguồn gốc nội dung của một item khi nạp từ bộ từ dựng sẵn.

    CỐ Ý không nằm trong `ItemCreateRequest`: người học không tự chứng nhận
    được nghĩa của chính mình. Chỉ luồng seed nội bộ truyền vào; item tạo qua
    API công khai để NULL.
    """

    meaning_confidence: str | None = Field(default=None, max_length=20)
    meaning_source: str | None = Field(default=None, max_length=20)
    example_source: str | None = Field(default=None, max_length=20)
    #: Bản dịch đi kèm câu ví dụ của bộ dựng sẵn — cùng nguồn với `example_source`.
    example_vi: str | None = None


class ItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    word_set_id: int
    word: str
    phonetic: str | None
    part_of_speech: str | None
    meaning: str
    example: str | None
    example_vi: str | None = None
    #: NULL với item người học tự nhập; xem `ItemProvenance`.
    meaning_confidence: str | None = None
    meaning_source: str | None = None
    example_source: str | None = None
    created_at: datetime


class ImportRowError(BaseModel):
    row: int  # số dòng dữ liệu (1-based, không tính header)
    message: str


class ImportReport(BaseModel):
    imported: int
    errors: list[ImportRowError]
