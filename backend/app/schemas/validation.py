"""Pilot — bài kiểm tra cuối (xem `validation_service`)."""
from __future__ import annotations

from pydantic import BaseModel


class ValidationStatus(BaseModel):
    open: bool                         # admin đã mở bài chưa (cấu hình validation_open)
    done: bool                         # người học đã nộp bài chưa
    in_progress_session_id: int | None
    eligible_items: int                # số từ đã học — nguồn để bốc đề
    size: int                          # số câu dự kiến
    min_items: int                     # dưới mức này thì chưa làm được


class ValidationQuestion(BaseModel):
    """Một câu gõ từ. KHÔNG kèm đáp án — đây là bài kiểm tra, không phải luyện tập."""

    item_id: int
    meaning: str
    part_of_speech: str | None
    first_letter: str
    length: int


class ValidationStart(BaseModel):
    session_id: int
    questions: list[ValidationQuestion]   # các câu CHƯA trả lời (vào lại thì còn lại bấy nhiêu)
