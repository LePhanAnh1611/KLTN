from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review_schedule import ReviewSchedule
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.dashboard import DashboardResponse
from app.services.gamification_service import compute_level, default_daily_item_goal
from app.services.mastery_service import mastered_item_ids


def get_dashboard(db: Session, user: User) -> DashboardResponse:
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one_or_none()
    xp = progress.xp if progress else 0
    streak_count = progress.streak_count if progress else 0
    items_mastered = len(mastered_item_ids(db, user.id))

    settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    # UC-10 luồng 1a: chưa đặt mục tiêu -> dùng mặc định thay vì để trống
    daily_item_goal = (settings.daily_item_goal if settings else None) or default_daily_item_goal()

    word_set_count = db.execute(
        select(func.count())
        .select_from(WordSet)
        .where(WordSet.owner_id == user.id, WordSet.deleted_at.is_(None))
    ).scalar_one()

    review_due_count = db.execute(
        select(func.count())
        .select_from(ReviewSchedule)
        .where(
            ReviewSchedule.user_id == user.id,
            ReviewSchedule.next_review_at <= datetime.now(timezone.utc),
        )
    ).scalar_one()

    level, xp_into_level, xp_for_next_level = compute_level(xp)

    return DashboardResponse(
        xp=xp,
        level=level,
        xp_into_level=xp_into_level,
        xp_for_next_level=xp_for_next_level,
        streak_count=streak_count,
        items_mastered=items_mastered,
        word_set_count=word_set_count,
        review_due_count=review_due_count,
        daily_item_goal=daily_item_goal,
    )
