"""UC-61 sinh thông báo in-app · UC-58 xem · UC-59 quản lý · UC-60 tùy chọn loại.

`notify()` là mắt xích chung: mọi sự kiện (mở huy hiệu, bình luận, nhắc ôn…) đều
đi qua đây để tôn trọng cấu hình của người dùng (E1) trước khi tạo NOTIFICATION.
Phần email của UC-61 nằm ở `email_service` (UC-62).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferences,
    NotificationResponse,
    NotificationType,
)

DEFAULT_LIMIT = 30

# Loại thông báo -> cột bật/tắt trong USER_SETTINGS (UC-60).
# Loại không có trong bảng này (VD 'system') luôn được gửi.
_PREF_COLUMN: dict[str, str] = {
    "review_due": "notify_review",
    "streak_risk": "notify_review",
    "achievement": "notify_achievement",
    "community": "notify_community",
}


def is_enabled(db: Session, user_id: int, type_: str) -> bool:
    """UC-61 E1 — người dùng có bật nhận loại thông báo này không."""
    column = _PREF_COLUMN.get(type_)
    if column is None:
        return True
    settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()
    return getattr(settings, column) if settings else True


def notify(
    db: Session,
    user_id: int,
    *,
    type_: NotificationType,
    title: str,
    body: str | None = None,
    link: str | None = None,
    commit: bool = True,
) -> Notification | None:
    """UC-61 — tạo thông báo in-app; trả None nếu người dùng đã tắt loại này.

    `commit=False` để gộp vào transaction của service gọi tới (VD complete_session).
    """
    if not is_enabled(db, user_id, type_):
        return None

    notification = Notification(
        user_id=user_id, type=type_, title=title, body=body, link=link
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    else:
        db.flush()
    return notification


def list_notifications(
    db: Session, user: User, *, unread_only: bool = False, limit: int = DEFAULT_LIMIT
) -> NotificationListResponse:
    """UC-58 — danh sách thông báo + số chưa đọc (badge chuông)."""
    filters = [Notification.user_id == user.id]
    if unread_only:
        filters.append(Notification.is_read.is_(False))

    rows = db.execute(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    ).scalars().all()

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in rows],
        unread_count=unread_count(db, user),
    )


def unread_count(db: Session, user: User) -> int:
    return db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
    ).scalar_one()


def _get_own_or_404(db: Session, user: User, notification_id: int) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông báo"
        )
    return notification


def mark_read(db: Session, user: User, notification_id: int) -> NotificationResponse:
    """UC-59 — đánh dấu một thông báo đã đọc."""
    notification = _get_own_or_404(db, user, notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return NotificationResponse.model_validate(notification)


def mark_all_read(db: Session, user: User) -> int:
    """UC-59 — đọc tất cả; trả số thông báo vừa đánh dấu."""
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount or 0


def delete_notification(db: Session, user: User, notification_id: int) -> None:
    """UC-59 — xóa hẳn một thông báo khỏi danh sách."""
    notification = _get_own_or_404(db, user, notification_id)
    db.delete(notification)
    db.commit()


def get_preferences(db: Session, user: User) -> NotificationPreferences:
    """UC-60 — tùy chọn nhận thông báo hiện tại."""
    settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings is None:
        return NotificationPreferences()
    return NotificationPreferences.model_validate(settings)


def update_preferences(
    db: Session, user: User, data: NotificationPreferences
) -> NotificationPreferences:
    """UC-60 — bật/tắt từng loại thông báo."""
    settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    settings.notify_review = data.notify_review
    settings.notify_achievement = data.notify_achievement
    settings.notify_community = data.notify_community
    db.commit()
    db.refresh(settings)
    return NotificationPreferences.model_validate(settings)
