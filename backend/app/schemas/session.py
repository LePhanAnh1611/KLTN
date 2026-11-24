from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# Các chế độ ôn xuyên thư viện: lấy từ nhiều bộ nên KHÔNG gắn word_set_id.
# srs_review = theo lịch (UC-33) · weak_review = theo mastery thấp (UC-86)
CROSS_LIBRARY_MODES = {"srs_review", "weak_review"}
# Chế độ có thể chạy CẢ trong một bộ lẫn xuyên thư viện. dkt_smart mở từ trang
# chủ ("Học N từ mới") học đúng các từ đã gợi ý — chúng có thể thuộc nhiều bộ.
WORD_SET_OPTIONAL_MODES = CROSS_LIBRARY_MODES | {"dkt_smart"}

# Pilot — các chế độ thẻ lật được phép kèm một câu hỏi CHẤM KHÁCH QUAN (chọn
# nghĩa / gõ từ) trước khi lật thẻ. Khi có, kết quả lượt là do hệ thống chấm,
# không phải người học tự khai "nhớ/quên" — đầu vào sạch hơn cho DKT và là thứ
# duy nhất dùng được để kiểm chứng mastery so với thực tế.
OBJECTIVE_CHECK_MODES = {"dkt_smart", "srs_review", "weak_review"}
OBJECTIVE_FORMATS = {"quiz", "typing"}


class SessionCreateRequest(BaseModel):
    word_set_id: int | None = None
    # UC-94: game_* là các chế độ trò chơi. Chúng KHÔNG phải dạng bài mới — mỗi
    # trò ánh xạ về một dạng bài đã có khi ghi INTERACTION (xem `game_service`).
    mode: str = Field(
        pattern=(
            "^(flashcard|quiz|cloze|typing|dictation|mixed|matching|dkt_smart"
            "|srs_review|weak_review|sm2|game_rain|game_spelling|game_match)$"
        )
    )
    # UC-35: bật để luyện lại mà không làm xê dịch lịch ôn đã có
    practice_only: bool = False

    @model_validator(mode="after")
    def _word_set_required_unless_cross_library(self) -> "SessionCreateRequest":
        if self.mode not in WORD_SET_OPTIONAL_MODES and self.word_set_id is None:
            raise ValueError(f"word_set_id là bắt buộc trừ các chế độ {sorted(WORD_SET_OPTIONAL_MODES)}")
        return self


class AnswerRequest(BaseModel):
    item_id: int
    # Only self-assessed flashcards/reviews use is_correct. Objective exercises
    # send the actual answer; the service grades against the owned item.
    is_correct: bool | None = None
    answer: str | None = None
    client_answer_id: UUID | None = None
    response_time_ms: int | None = Field(default=None, ge=0)
    exercise_format: str | None = Field(default=None, max_length=30)
    # UC-34: mức đánh giá SM-2 (nếu có -> lập lịch bằng SM-2 thay vì mastery-based)
    sm2_rating: str | None = Field(default=None, pattern="^(again|hard|good|easy)$")
    #: Pilot — client gửi lại `RecommendedItem.selection` của từ này (chỉ có
    #: nghĩa ở phiên 'Học thông minh'; các chế độ khác do server tự gán).
    selection_reason: Literal["band", "explore"] | None = None


class SessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    word_set_id: int | None
    mode: str | None
    practice_only: bool
    status: str
    started_at: datetime
    ended_at: datetime | None
    item_count: int | None
    correct_count: int | None


class ActiveSessionResponse(BaseModel):
    session: SessionResponse | None
    answered_item_ids: list[int]


class WrongItem(BaseModel):
    item_id: int
    word: str
    meaning: str


class SessionSummary(BaseModel):
    session_id: int
    total_answered: int
    correct_count: int
    wrong_count: int
    accuracy: float  # 0.0 - 1.0
    duration_seconds: int
    mastered_count: int  # UC-30/BR-01: đạt ngưỡng mastery VÀ đủ lượt trả lời đúng
    xp_earned: int       # UC-46: XP nhận được từ phiên
    streak_count: int = 0        # UC-47: chuỗi ngày học sau phiên này
    #: True khi đây là phiên ĐẦU TIÊN trong ngày -> chuỗi vừa +1, đáng báo
    streak_extended: bool = False
    new_achievements: list[str] = []  # UC-48: tên huy hiệu vừa mở khóa
    wrong_items: list[WrongItem]


class SessionHistoryRow(BaseModel):
    """UC-45 — một dòng nhật ký học tập."""

    id: int
    mode: str | None
    status: str
    word_set_id: int | None
    word_set_name: str | None      # None = phiên xuyên thư viện (ôn lịch / điểm yếu)
    started_at: datetime
    ended_at: datetime | None
    item_count: int
    correct_count: int
    accuracy: float                # 0.0 - 1.0
    xp_earned: int
    duration_seconds: int | None


class SessionHistoryResponse(BaseModel):
    items: list[SessionHistoryRow]
    total: int
    page: int
    page_size: int
    # Tổng hợp trên TOÀN BỘ lịch sử, không chỉ trang hiện tại
    total_sessions: int
    total_items_answered: int
    total_xp: int


class ResumableSession(BaseModel):
    """Phiên đang dở gần nhất — để trang chủ mời người học học tiếp (UC-31)."""

    session_id: int
    mode: str | None
    word_set_id: int | None
    word_set_name: str | None
    started_at: datetime
    answered_count: int


class QuizForItemsRequest(BaseModel):
    """Pilot — xin câu trắc nghiệm cho đúng danh sách từ sắp học/ôn."""

    item_ids: list[int] = Field(min_length=1, max_length=100)
