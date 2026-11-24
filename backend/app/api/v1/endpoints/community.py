"""UC-49..UC-53 — feed cộng đồng: đăng bài, bình luận, thích, xóa, báo cáo."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.community import (
    CommentCreate,
    CommentResponse,
    LeaderboardResponse,
    LeaderboardScope,
    PostCard,
    PostCreate,
    PostListResponse,
    ReactionResponse,
)
from app.schemas.report import ReportRequest, ReportResponse
from app.services import community_service, leaderboard_service, report_service

router = APIRouter()


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    scope: LeaderboardScope = "all",
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardResponse:
    """UC-54 — bảng xếp hạng theo XP (toàn thời gian hoặc 7 ngày gần nhất)."""
    return leaderboard_service.get_leaderboard(db, current_user, scope=scope, limit=limit)


@router.get("/posts", response_model=PostListResponse)
def list_feed(
    post_type: str | None = None,
    author_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """UC-49 — bảng tin cộng đồng (chỉ bài đã duyệt)."""
    return community_service.list_feed(
        db, current_user, post_type=post_type, author_id=author_id,
        page=page, page_size=page_size,
    )


@router.post("/posts", response_model=PostCard, status_code=status.HTTP_201_CREATED)
def create_post(
    data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostCard:
    """UC-49 — đăng bài (loại, nội dung, URL ảnh tùy chọn)."""
    return community_service.create_post(db, current_user, data)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-52 — gỡ bài của chính mình."""
    community_service.delete_post(db, current_user, post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
def list_comments(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentResponse]:
    """UC-50 — danh sách bình luận của bài."""
    return community_service.list_comments(db, current_user, post_id)


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    post_id: int,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentResponse:
    """UC-50 — bình luận vào bài viết."""
    return community_service.add_comment(db, current_user, post_id, data)


@router.post("/posts/{post_id}/like", response_model=ReactionResponse)
def toggle_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReactionResponse:
    """UC-51 — thích / bỏ thích bài viết."""
    return community_service.toggle_reaction(db, current_user, post_id)


@router.post("/posts/{post_id}/report", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def report_post(
    post_id: int,
    data: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """UC-53 — báo cáo bài viết vi phạm (vào hàng đợi Admin, UC-78)."""
    community_service.get_visible_post(db, post_id)  # 404 nếu bài không còn hiển thị
    return report_service.create_report(
        db, current_user,
        target_type=report_service.TARGET_POST, target_id=post_id, data=data,
    )
