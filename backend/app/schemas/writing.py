"""UC-37 luyện viết Việt→Anh · UC-38 sổ tay câu."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WritingPrompt(BaseModel):
    item_id: int
    word: str
    prompt_vi: str
    # Câu ví dụ gốc — chỉ hiện SAU khi nộp, để không lộ đáp án
    reference_en: str | None


class WritingSubmitRequest(BaseModel):
    prompt_vi: str = Field(min_length=1, max_length=500)
    answer_en: str = Field(min_length=1, max_length=1000)


class WritingResult(BaseModel):
    id: int
    prompt_vi: str
    answer_en: str
    score: float | None
    feedback: str | None
    suggestion: str | None
    # 'llm' = mô hình ngôn ngữ chấm · 'heuristic' = bộ kiểm tra máy móc dự phòng.
    # Giao diện PHẢI hiển thị thông tin này, không trình bày heuristic như AI.
    grader: str
    created_at: datetime


class NoteCreate(BaseModel):
    text_en: str = Field(min_length=1, max_length=1000)
    text_vi: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)
    submission_id: int | None = None


class NoteUpdate(BaseModel):
    text_en: str | None = Field(default=None, min_length=1, max_length=1000)
    text_vi: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


class NoteRow(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    text_en: str
    text_vi: str | None
    note: str | None
    submission_id: int | None
    created_at: datetime
