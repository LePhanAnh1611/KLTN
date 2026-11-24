"""UC-11 — kiểm tra trình độ đầu vào (placement test)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class PlacementQuestionOut(BaseModel):
    """Câu hỏi gửi cho người học — KHÔNG kèm đáp án đúng."""

    id: int
    cefr_level: str
    word: str
    options: list[str]      # đã trộn sẵn, gồm 1 đáp án đúng + các nhiễu


class PlacementAnswer(BaseModel):
    question_id: int
    answer: str


class PlacementSubmit(BaseModel):
    answers: list[PlacementAnswer]


class PlacementLevelBreakdown(BaseModel):
    cefr_level: str
    answered: int
    correct: int


class PlacementResult(BaseModel):
    """Kết quả ước lượng + trình độ đầu vào đã ghi nhận."""

    estimated_level: str
    entry_cefr_level: str
    answered_count: int
    correct_count: int
    per_level: list[PlacementLevelBreakdown]
    skipped: bool = False


class PlacementStatus(BaseModel):
    has_placement: bool
    entry_cefr_level: str | None
    completed_at: datetime | None = None
    question_count: int = Field(default=0, description="Số câu hỏi đang có trong ngân hàng")


# ---- UC-11 quản trị ngân hàng câu hỏi (Admin) ----


class PlacementQuestionAdminRow(BaseModel):
    """Bản đầy đủ cho Admin — CÓ đáp án đúng, khác `PlacementQuestionOut`."""

    model_config = {"from_attributes": True}

    id: int
    cefr_level: str
    word: str
    correct_meaning: str
    distractors: list[str]
    is_active: bool


class PlacementQuestionCreate(BaseModel):
    cefr_level: CefrLevel
    word: str = Field(min_length=1, max_length=200)
    correct_meaning: str = Field(min_length=1, max_length=300)
    # Đúng 3 nhiễu: bài thi hiển thị 4 lựa chọn (1 đúng + 3 nhiễu)
    distractors: list[str] = Field(min_length=3, max_length=3)
    is_active: bool = True


class PlacementQuestionUpdate(BaseModel):
    """Gửi field nào đổi field đó."""

    cefr_level: CefrLevel | None = None
    word: str | None = Field(default=None, min_length=1, max_length=200)
    correct_meaning: str | None = Field(default=None, min_length=1, max_length=300)
    distractors: list[str] | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


class PlacementBankStats(BaseModel):
    """Số câu đang bật theo từng mức — Admin cần thấy mức nào đang mỏng."""

    cefr_level: str
    active_count: int
    total_count: int
