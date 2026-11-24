"""Lưu kết quả luyện phát âm (mở rộng UC-29)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PronunciationAttemptCreate(BaseModel):
    item_id: int
    score: float = Field(ge=0, le=100)
    transcript: str | None = Field(default=None, max_length=300)


class PronunciationAttemptRow(BaseModel):
    id: int
    item_id: int
    word: str
    meaning: str
    score: float
    transcript: str | None
    created_at: datetime


class PronunciationStats(BaseModel):
    """Tổng hợp để người học thấy mình tiến bộ hay giậm chân."""

    total_attempts: int
    words_practiced: int
    average_score: float
    best_score: float
    recent: list[PronunciationAttemptRow]


class ItemBestScore(BaseModel):
    """Kỷ lục phát âm của một từ (cả đọc từ lẫn đọc câu), thang 0–100."""

    item_id: int
    best_score: float
    attempts: int


# ---- Đọc theo câu mẫu (chấm trên máy chủ bằng Whisper) ----


class WordCheckOut(BaseModel):
    expected: str
    heard: str | None
    ok: bool
    confidence: float | None


class AspectOut(BaseModel):
    key: str            # accuracy | clarity | fluency
    label: str
    level: int = Field(ge=1, le=4)
    level_label: str
    detail: str
    suggestion: str


class ReadAloudResponse(BaseModel):
    """Kết quả đọc câu mẫu.

    KHÔNG dùng rubric 4 tiêu chí của nói tự do: C3 (ngữ pháp & từ vựng) và C4
    (mạch lạc & bám đề) giả định người học tự tạo lời, đọc lại câu cho sẵn thì
    hai tiêu chí đó vô nghĩa.
    """

    attempt_id: int | None
    item_id: int
    word: str
    expected_text: str
    transcript: str

    accuracy: float                 # 0..1 tỉ lệ từ đọc đúng
    clarity: float                  # 0..1 độ tin cậy ASR trung bình
    overall_level: int = Field(ge=1, le=4)
    aspects: list[AspectOut]

    words: list[WordCheckOut]
    missed_words: list[str]
    extra_words: list[str]

    audio_metrics: dict
    feedback: str
    warnings: list[str] = []


class ReadAloudHistoryRow(BaseModel):
    id: int
    item_id: int
    word: str
    kind: str
    score: float
    transcript: str | None
    target_text: str | None
    detail: dict | None
    created_at: datetime
