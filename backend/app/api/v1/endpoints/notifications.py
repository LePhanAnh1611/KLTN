"""UC-58 xem thông báo · UC-59 quản lý · UC-60 tùy chọn loại."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferences,
    NotificationResponse,
)
from app.services import notification_service

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """UC-58 — danh sách thông báo + số chưa đọc (badge chuông)."""
    return notification_service.list_notifications(
        db, current_user, unread_only=unread_only, limit=limit,
    )


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferences:
    """UC-60 — tùy chọn nhận thông báo."""
    return notification_service.get_preferences(db, current_user)


@router.put("/preferences", response_model=NotificationPreferences)
def update_preferences(
    data: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferences:
    """UC-60 — bật/tắt từng loại thông báo."""
    return notification_service.update_preferences(db, current_user, data)


@router.post("/read-all", response_model=dict)
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """UC-59 — đánh dấu tất cả đã đọc."""
    return {"marked": notification_service.mark_all_read(db, current_user)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    """UC-59 — đánh dấu một thông báo đã đọc."""
    return notification_service.mark_read(db, current_user, notification_id)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-59 — xóa một thông báo."""
    notification_service.delete_notification(db, current_user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
