"""UC-84 — Lộ trình học cá nhân hóa."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

StageState = Literal["mastered", "achieved", "current", "in_progress", "locked"]


class RoadmapStage(BaseModel):
    id: int
    title: str
    cefr_level: str
    order_index: int
    word_set_id: int          # bộ từ gốc của chặng (do Admin quản lý)
    #: Lộ trình v2: 'topic' (chủ đề) | 'core' (cốt lõi). None = chặng v1.
    track: str | None = None
    topic: str | None = None  # tên chủ đề khi track = 'topic'
    state: StageState
    progress_pct: float       # 0..100
    items_mastered: int
    items_total: int
    # Số từ cần đạt để qua chặng = ceil(stage_mastered_ratio * items_total) —
    # chặng xong ở 80% chứ không phải 100%, nên vòng tiến độ đo theo con số này.
    items_needed: int = 0
    items_learning: int = 0   # đã học >= 1 lần nhưng chưa đạt M_high
    is_recommended: bool      # BR-RM-03 — chỉ đúng MỘT chặng có cờ này

    # Ngoài schema mục 6: bản sao trong thư viện người học (Q1/Q2 — mastery gắn
    # theo item bản sao). null = chưa tải, frontend sẽ tải rồi mới vào học.
    user_word_set_id: int | None = None
    is_skipped: bool = False


class RoadmapResponse(BaseModel):
    entry_level: str
    #: UC-10 — mục tiêu CEFR người học tự đặt ở Cài đặt. None = chưa đặt.
    target_level: str | None = None
    stages: list[RoadmapStage]


class StageWord(BaseModel):
    """Một từ trong bảng tổng kết chặng."""

    item_id: int
    word: str
    meaning: str
    mastery: float


class StageSummary(BaseModel):
    """Tổng kết một chặng — hiện khi người học hoàn thành, thay cho việc chặng
    lặng lẽ đổi màu mà không nói gì.

    Số liệu chia hai nhóm cố ý:
    - `items_*` / `strongest` / `weakest` đọc từ KNOWLEDGE_STATE (trạng thái HIỆN TẠI)
    - `answers_*` đọc từ INTERACTION (QUÁ TRÌNH đi tới trạng thái đó)
    Hai nhóm này trả lời hai câu hỏi khác nhau: "giờ tôi thuộc bao nhiêu" và
    "tôi đã làm bao nhiêu lượt, đúng bao nhiêu".
    """

    stage_id: int
    title: str
    cefr_level: str
    state: StageState
    is_complete: bool

    items_total: int
    items_mastered: int
    progress_pct: float

    answers_total: int
    answers_correct: int
    accuracy: float                 # 0.0 - 1.0

    strongest: list[StageWord]      # nắm chắc nhất — "điểm mạnh"
    weakest: list[StageWord]        # dưới ngưỡng điểm yếu, nên ôn lại

    next_stage_id: int | None
    next_stage_title: str | None
