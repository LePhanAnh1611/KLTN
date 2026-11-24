from __future__ import annotations

from pydantic import BaseModel


class QuizQuestion(BaseModel):
    item_id: int
    word: str
    options: list[str]  # 4 nghĩa đã xáo trộn
    correct_index: int


class ClozeQuestion(BaseModel):
    """UC-28 — điền khuyết: một câu ví dụ đã khoét mất từ cần điền."""

    item_id: int
    sentence: str        # câu ví dụ, chỗ trống là "____"
    answer: str          # phản hồi luyện tập; backend chấm lại đáp án khi ghi Interaction
    hint: str            # nghĩa tiếng Việt, để không bí hoàn toàn


class TypingQuestion(BaseModel):
    """UC-89 — gõ từ: thấy nghĩa tiếng Việt, tự gõ lại từ tiếng Anh.

    Khác trắc nghiệm/ghép cặp ở chỗ đây là **nhớ chủ động**: không có sẵn đáp án
    để nhận ra, người học phải lôi từ trong đầu ra. Cũng khác điền khuyết ở chỗ
    KHÔNG cần câu ví dụ, nên chạy được trên mọi bộ từ.
    """

    item_id: int
    meaning: str              # đề bài: nghĩa tiếng Việt
    answer: str               # phản hồi luyện tập; backend chấm lại khi ghi Interaction
    part_of_speech: str | None
    first_letter: str         # gợi ý chính tả: chữ cái đầu
    length: int               # số ký tự, để vẽ ô trống


class MatchPair(BaseModel):
    item_id: int
    word: str
    meaning: str


class MatchingRound(BaseModel):
    """UC-28 — ghép cặp: một lượt gồm vài từ và các nghĩa đã xáo trộn."""

    pairs: list[MatchPair]          # thứ tự hiển thị cột từ
    shuffled_meanings: list[str]    # cột nghĩa, đã xáo để không khớp theo hàng
