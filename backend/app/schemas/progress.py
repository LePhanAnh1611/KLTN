from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MasteryBand(BaseModel):
    label: str
    count: int


class WeakItem(BaseModel):
    item_id: int
    word: str
    meaning: str
    word_set_name: str
    mastery: float


class MasteryPoint(BaseModel):
    """Một lượt trả lời trên đường cong học tập của một từ."""

    answered_at: datetime
    #: Mastery hệ thống nắm giữ NGAY TRƯỚC lượt này. None = chưa có dự đoán nào
    #: (lần đầu gặp từ, hoặc lượt xảy ra trước khi cột này tồn tại).
    mastery: float | None
    is_correct: bool
    #: 'model' = DKT chấm · 'prior' = giá trị cold-start · None = chưa có
    source: str | None
    exercise_format: str | None


class MasteryHistory(BaseModel):
    """UC-92 — đường cong học tập của MỘT từ, dựng lại từ INTERACTION.

    Không cần bảng lịch sử riêng: `INTERACTION.predicted_mastery` (thêm cho
    UC-70 để đo prequential) đã ghi sẵn giá trị tại từng mốc thời gian.
    """

    item_id: int
    word: str
    meaning: str
    current_mastery: float | None
    mastered_threshold: float
    total_answers: int
    #: Số lượt chưa có dự đoán — nói thẳng ra thay vì vẽ liền một đường giả.
    answers_without_prediction: int
    points: list[MasteryPoint]


class ProgressResponse(BaseModel):
    level: int
    level_title: str
    xp: int
    xp_into_level: int
    xp_for_next_level: int
    streak_count: int
    today_xp: int             # UC-41: XP tích trong hôm nay
    daily_xp_goal: int        # UC-41: định mức XP/ngày
    daily_goal_reached: bool  # UC-41: đã đạt mục tiêu hôm nay chưa
    total_items: int      # tổng từ trong thư viện (bộ sở hữu, chưa xóa)
    learned_items: int    # đã có knowledge state (đã học ít nhất 1 lần)
    mastered_items: int   # mastery >= 0.9 (BR-01)
    mastery_distribution: list[MasteryBand]
    weak_items: list[WeakItem]  # mastery thấp nhất (điểm yếu)
