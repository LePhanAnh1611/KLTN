from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.review import ReviewCalendar, ReviewItem, WeakReviewItem, ReviewCleanupResult
from app.services import review_service

router = APIRouter()


@router.get("/calendar", response_model=ReviewCalendar)
def calendar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewCalendar:
    """UC-36 — lịch ôn theo tuần (hôm nay/ngày mai/tuần này)."""
    return review_service.get_calendar(db, current_user)


@router.get("/due", response_model=list[ReviewItem])
def due(
    limit: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReviewItem]:
    """UC-33 — item đến hạn ôn (để bắt đầu phiên ôn SRS)."""
    return review_service.get_due_items(db, current_user, limit)


@router.post("/pause-lower-level", response_model=ReviewCleanupResult)
def pause_lower_level(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewCleanupResult:
    return ReviewCleanupResult(paused_count=review_service.pause_lower_level_reviews(db, current_user))


@router.get("/weak", response_model=list[WeakReviewItem])
def weak(
    limit: int | None = Query(default=None, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WeakReviewItem]:
    """UC-86 — các từ mastery thấp nhất, để mở phiên ôn đúng chỗ yếu (không theo lịch)."""
    return review_service.get_weak_items(db, current_user, limit)
