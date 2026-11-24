"""UC-19/20/21 khám phá & tải · UC-22 nổi bật · UC-23 đánh giá · UC-24 báo cáo."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.discover import (
    PublicListResponse,
    PublicWordSetCard,
    PublicWordSetDetail,
    SortOption,
    TagCount,
)
from app.schemas.admin import CategoryResponse
from app.schemas.rating import RatingRequest, RatingSummary
from app.schemas.report import ReportRequest, ReportResponse
from app.schemas.word_set import WordSetResponse
from app.services import (
    category_service,
    discover_service,
    rating_service,
    report_service,
    tag_service,
    word_set_service,
)

router = APIRouter()


@router.get("", response_model=PublicListResponse)
def list_public(
    q: str | None = Query(default=None, description="Tìm theo tên"),
    category: str | None = None,
    difficulty: str | None = None,
    tag: str | None = Query(default=None, description="UC-96: lọc theo nhãn"),
    sort: SortOption = "popular",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicListResponse:
    return discover_service.list_public(
        db, current_user, search=q, category=category, difficulty=difficulty,
        tag=tag, sort=sort, page=page, page_size=page_size,
    )


@router.get("/tags", response_model=list[TagCount])
def list_tags(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TagCount]:
    """UC-96: nhãn phổ biến kèm số bộ công khai — dùng dựng dải lọc ở Khám phá.

    Chỉ đếm bộ đang công khai: hiện một nhãn mà bấm vào không ra gì là lỗi giao
    diện tệ hơn cả việc không hiện nhãn đó.
    """
    return [TagCount(tag=t, count=n) for t, n in tag_service.popular_tags(db, limit)]


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CategoryResponse]:
    """UC-76 → UC-19: danh mục đang bật, dùng cho bộ lọc & ô chọn khi tạo bộ từ."""
    return [
        CategoryResponse.model_validate(c)
        for c in category_service.list_categories(db)
    ]


@router.get("/featured", response_model=list[PublicWordSetCard])
def list_featured(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PublicWordSetCard]:
    """UC-22 — bộ từ nổi bật (khai báo TRƯỚC /{word_set_id} để không bị nuốt path)."""
    return discover_service.list_featured(db, current_user)


@router.get("/{word_set_id}", response_model=PublicWordSetDetail)
def get_detail(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicWordSetDetail:
    return discover_service.get_public_detail(db, current_user, word_set_id)


@router.post("/{word_set_id}/download", response_model=WordSetResponse, status_code=status.HTTP_201_CREATED)
def download(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    return discover_service.clone_word_set(db, current_user, word_set_id)


@router.get("/{word_set_id}/ratings", response_model=RatingSummary)
def get_ratings(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RatingSummary:
    """UC-23 — điểm trung bình + đánh giá của chính mình + nhận xét gần đây."""
    return rating_service.get_summary(db, current_user, word_set_id)


@router.put("/{word_set_id}/rating", response_model=RatingSummary)
def rate_word_set(
    word_set_id: int,
    data: RatingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RatingSummary:
    """UC-23 — chấm sao (gửi lại = sửa đánh giá cũ)."""
    return rating_service.upsert_rating(db, current_user, word_set_id, data)


@router.post("/{word_set_id}/report", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def report_word_set(
    word_set_id: int,
    data: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """UC-24 — báo cáo bộ từ vi phạm (vào hàng đợi Admin, UC-78)."""
    word_set_service.get_public_word_set(db, word_set_id)  # 404 nếu bộ không còn khả dụng
    return report_service.create_report(
        db, current_user,
        target_type=report_service.TARGET_WORD_SET, target_id=word_set_id, data=data,
    )
