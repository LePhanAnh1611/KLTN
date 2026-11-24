"""Schema cho trang chủ học viên — tổng hợp dữ liệu đã có, chỉ đọc.

Không có thực thể mới: mọi con số đều suy ra từ INTERACTION / KNOWLEDGE_STATE /
REVIEW_SCHEDULE / USER_PROGRESS sẵn có.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DailyGoal(BaseModel):
    """UC-10/UC-41 — mục tiêu số từ trong ngày, VD 14/20."""

    done: int
    target: int
    reached: bool


class GamificationSummary(BaseModel):
    """UC-46/47/48 — số liệu cho topbar & sidebar."""

    xp: int
    level: int
    level_title: str
    xp_into_level: int
    xp_for_next_level: int
    streak_count: int
    daily_goal: DailyGoal


class StatsOverview(BaseModel):
    """UC-40 — mức nắm vững toàn thư viện.

    `mastered` theo BR-01 (đạt ngưỡng mastery và đủ lượt đúng). `in_progress` là từ đã học
    ít nhất một lần nhưng chưa đạt ngưỡng; `not_started` là từ chưa có knowledge
    state nào.
    """

    total_items: int
    mastered: int
    in_progress: int
    not_started: int
    mastery_percent: float      # mastered / total_items * 100, làm tròn 1 chữ số


class CourseProgress(BaseModel):
    """UC-40/41 — một bộ từ trong thư viện kèm % hoàn thành."""

    id: int
    name: str
    cover_image_url: str | None = None
    #: Mức CEFR của bộ — bản đồ lộ trình gom bộ theo trường này thay vì đoán
    #: mức bằng cách đọc tên bộ ở phía React.
    cefr_level: str | None = None
    total_items: int
    mastered_items: int
    #: Đã học >= 1 lần nhưng chưa thuộc — để thanh tiến độ ghi nhận công sức
    #: trước khi từ đạt ngưỡng BR-01.
    learning_items: int = 0
    percent: float


class RecommendedWord(BaseModel):
    item_id: int
    word: str
    meaning: str
    word_set_id: int
    word_set_name: str
    predicted_p: float


class TodayRecommendation(BaseModel):
    """UC-65 — từ vừa sức theo BR-03; `degraded` = service DKT không sẵn sàng nên
    điểm là cold-start prior (UC-69) chứ không phải dự đoán mô hình."""

    count: int
    band_low: float
    band_high: float
    degraded: bool
    items: list[RecommendedWord]
    #: Số từ được học LẦN ĐẦU trong hôm nay (theo múi giờ người học). >= 1 thì
    #: bước "Học từ mới" của phiên hôm nay coi như xong — trước đây bước này không
    #: bao giờ được đánh dấu xong dù đã học bộ mới.
    new_learned_today: int = 0


class ReviewDay(BaseModel):
    """UC-36/66 — một ngày trong tháng có từ tới hạn ôn."""

    date: date
    due_count: int


class UpcomingReview(BaseModel):
    """UC-36/66 — mục ôn sắp tới, gom theo bộ từ."""

    id: int                 # word_set_id
    title: str              # tên bộ từ
    group: str | None       # danh mục của bộ từ
    due_count: int
    scheduled_at: datetime  # thời điểm tới hạn sớm nhất trong nhóm
