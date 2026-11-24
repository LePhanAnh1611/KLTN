"""UC-34 — SM-2 baseline (thuật toán giãn cách Anki cổ điển).

Đây là baseline ĐỐI CHIẾU với lập lịch mastery-based (UC-66/DKT). Người học tự
đánh giá độ nhớ bằng 4 mức; SM-2 cập nhật interval/ease/repetitions — KHÔNG dùng DKT.

4 mức -> quality (SM-2 0..5): Lại=1, Khó=3, Tốt=4, Dễ=5.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review_schedule import ReviewSchedule

RATING_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}
MIN_EASE = 1.3


def sm2_step(quality: int, interval: int, ease: float, reps: int) -> tuple[int, float, int]:
    """Một bước SM-2 -> (interval_days, ease_factor, repetitions) mới."""
    if quality < 3:  # Lại (fail): về đầu
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    # cập nhật ease factor (công thức SM-2), sàn 1.3
    ease = max(MIN_EASE, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return interval, round(ease, 2), reps


def schedule_review_sm2(db: Session, user_id: int, item_id: int, rating: str) -> ReviewSchedule:
    """Upsert REVIEW_SCHEDULE theo SM-2 từ mức đánh giá của người học."""
    quality = RATING_QUALITY[rating]
    rs = db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == user_id, ReviewSchedule.item_id == item_id
        )
    ).scalar_one_or_none()

    prev_interval = rs.interval_days if rs else 1
    prev_ease = float(rs.ease_factor) if rs else 2.5
    prev_reps = rs.repetitions if rs else 0

    interval, ease, reps = sm2_step(quality, prev_interval, prev_ease, prev_reps)
    next_at = datetime.now(timezone.utc) + timedelta(days=interval)

    if rs is None:
        rs = ReviewSchedule(user_id=user_id, item_id=item_id, next_review_at=next_at,
                            interval_days=interval, ease_factor=ease, repetitions=reps)
        db.add(rs)
    else:
        rs.next_review_at = next_at
        rs.interval_days = interval
        rs.ease_factor = ease
        rs.repetitions = reps
    rs.is_paused = False
    db.commit()
    return rs
