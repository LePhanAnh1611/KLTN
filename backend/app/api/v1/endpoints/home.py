"""API cho trang chủ học viên — chỉ đọc, tổng hợp dữ liệu đã có.

Router không chứa logic: mọi phép tính nằm ở `home_service`.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.home import (
    CourseProgress,
    GamificationSummary,
    ReviewDay,
    StatsOverview,
    TodayRecommendation,
    UpcomingReview,
)
from app.schemas.recommend import RecommendedItem
from app.services import home_service

router = APIRouter()


@router.get("/gamification/summary", response_model=GamificationSummary, tags=["home"])
def get_gamification_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GamificationSummary:
    """UC-46/47/48 — streak, XP, cấp hiện tại, mục tiêu từ trong ngày."""
    return home_service.get_gamification_summary(db, current_user)


@router.get("/stats/overview", response_model=StatsOverview, tags=["home"])
def get_stats_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsOverview:
    """UC-40 — mức nắm vững toàn thư viện (mastery đã lưu, không gọi lại DKT)."""
    return home_service.get_stats_overview(db, current_user)


@router.get("/progress/courses", response_model=list[CourseProgress], tags=["home"])
def list_course_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseProgress]:
    """UC-40/41 — bộ từ đang học kèm % hoàn thành."""
    return home_service.list_course_progress(db, current_user)


@router.get("/recommendations/today", response_model=TodayRecommendation, tags=["home"])
def get_today_recommendation(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TodayRecommendation:
    """UC-65/69 — từ vừa sức hôm nay theo BR-03 (ngưỡng lấy từ cấu hình)."""
    return home_service.get_today_recommendation(db, current_user, limit=limit)


@router.get("/recommendations/today/items", response_model=list[RecommendedItem], tags=["home"])
def get_today_study_items(
    ids: str = Query(
        pattern=r"^\d+(,\d+)*$", max_length=1000,
        description="id các từ trang chủ đã gợi ý, phân tách bằng dấu phẩy",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendedItem]:
    """Nội dung phiên "Học N từ mới" mở từ trang chủ — đúng các từ đã gợi ý,
    không chọn lại (xem `home_service.get_today_study_items`)."""
    item_ids = [int(x) for x in ids.split(",")]
    return home_service.get_today_study_items(db, current_user, item_ids)


@router.get("/review-schedules", response_model=list[ReviewDay], tags=["home"])
def get_review_days(
    month: str = Query(pattern=r"^\d{4}-\d{2}$", description="Tháng dạng YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReviewDay]:
    """UC-36/66 — các ngày trong tháng có từ tới hạn ôn + số lượng."""
    try:
        return home_service.get_review_days(db, current_user, month)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get("/review-schedules/upcoming", response_model=list[UpcomingReview], tags=["home"])
def list_upcoming_reviews(
    limit: int = Query(default=3, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UpcomingReview]:
    """UC-36/66 — vài mục ôn sắp tới, gom theo bộ từ, thời gian tăng dần."""
    return home_service.list_upcoming_reviews(db, current_user, limit=limit)
