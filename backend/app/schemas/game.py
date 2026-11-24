"""UC-94 — trò chơi từ vựng."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GameDefinition(BaseModel):
    key: str
    name: str
    description: str
    #: Chế độ phiên học cần tạo để chơi trò này (mọi lượt trả lời vẫn ghi
    #: INTERACTION qua luồng phiên bình thường — BR-05).
    session_mode: str
    #: Dạng bài thật gửi cho DKT. Trả ra để giao diện hiển thị được, và để bất
    #: kỳ ai đọc API cũng thấy trò chơi không phải một dạng bài mới.
    exercise_format: str
    #: Endpoint bài tập dùng làm nguồn đề ('typing' | 'matching').
    source: str
    best_score: int | None = None
    plays: int = 0


class GameScoreRequest(BaseModel):
    score: int = Field(ge=0)
    #: Phiên học đã chơi — để đối chiếu khi cần truy vết, không bắt buộc.
    session_id: int | None = None


class GameScoreResult(BaseModel):
    game: str
    score: int
    best_score: int
    is_new_best: bool
    plays: int
    rank: int


class GameLeaderboardRow(BaseModel):
    rank: int
    user_id: int
    display_name: str
    best_score: int
    best_at: datetime
