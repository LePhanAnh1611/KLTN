"""UC-93 — kết quả so sánh lịch ôn DKT với SM-2.

Chỉ là lớp đọc: thí nghiệm chạy offline ở `ml/src/schedule_sim.py`, backend
không tính lại. Mô phỏng 60 ngày cho hàng trăm người học không phải việc của
một request HTTP, và kết quả phải TÁI LẬP ĐƯỢC — số hiện trên màn Vận hành phải
đúng là số nằm trong file đã commit, không phải số vừa sinh ra lúc bấm.
"""
from __future__ import annotations

from pydantic import BaseModel


class SchedulerArm(BaseModel):
    """Một nhánh thi đấu: một bộ lập lịch ở một mức ngân sách."""
    scheduler: str            # sm2 | dkt | fixed
    budget: int               # số lượt trả lời mỗi ngày
    pool: int                 # kích thước kho từ của người học
    introduced: int           # số từ đã đưa vào học (giống nhau ở mọi nhánh)
    reviews: int              # tổng số lượt ôn đã tiêu
    recall_end: float         # số từ còn nhớ kỳ vọng, ngay khi kết thúc
    recall_delayed: float     # ... sau khi nghỉ hẳn (chỉ số CHÍNH)
    mastered_delayed: int
    recall_per_100_reviews: float
    wasted_pct: float         # ôn khi vẫn còn nhớ chắc (phí công)
    late_pct: float           # ôn khi đã quên (quay lại quá muộn)
    mean_gap_days: float
    mean_p_at_review: float
    daily_recall: list[float]


class SchedulerGap(BaseModel):
    """Chênh lệch ghép cặp theo từng người học, kèm khoảng tin cậy bootstrap."""
    key: str                  # ví dụ "dkt_vs_sm2@b20p300"
    mean_diff: float
    ci_low: float
    ci_high: float
    win_rate: float
    n_learners: int

    @property
    def significant(self) -> bool:
        return self.ci_low > 0 or self.ci_high < 0


class SchedulerSetup(BaseModel):
    learners: int
    horizon_days: int
    delay_days: int
    budgets: list[int]
    main_budget: int
    pools: list[int]
    main_pool: int
    mastered_threshold: float
    n_words: int
    model: str
    seconds: float


class SchedulerComparison(BaseModel):
    generated_at: str
    setup: SchedulerSetup
    memory_model: dict[str, object]
    arms: list[SchedulerArm]
    gaps: list[SchedulerGap]
