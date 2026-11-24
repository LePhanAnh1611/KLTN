"""UC-82 gửi thông báo hàng loạt · UC-80 quản lý hàng đợi email (Admin).

Broadcast đi qua đúng mắt xích UC-61 (`notification_service.notify`) nên vẫn tôn
trọng cấu hình người nhận; loại 'system' không tắt được nên mọi người đều nhận.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.email_queue import EmailQueue
from app.models.user import User
from app.schemas.admin import (
    BroadcastRequest,
    BroadcastResult,
    EmailQueueListResponse,
    EmailQueueRow,
)
from app.services import audit_service, email_service, notification_service

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# --- UC-82 broadcast ---------------------------------------------------------

def send_broadcast(db: Session, admin: User, data: BroadcastRequest) -> BroadcastResult:
    """Tạo NOTIFICATION (và tùy chọn email) hàng loạt cho nhóm người nhận."""
    if data.audience == "role" and not data.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần chọn vai trò khi gửi theo nhóm",
        )

    filters = [User.is_active.is_(True)]
    if data.audience == "role":
        filters.append(User.role == data.role)

    recipients = db.execute(select(User).where(*filters)).scalars().all()

    notifications = 0
    emails = 0
    for user in recipients:
        created = notification_service.notify(
            db, user.id, type_="system", title=data.title,
            body=data.body, link=data.link, commit=False,
        )
        if created is not None:
            notifications += 1
        if data.send_email:
            email_service.enqueue(
                db, user, to_email=user.email, subject=data.title,
                body=data.body or data.title, template="broadcast", commit=False,
            )
            emails += 1

    audit_service.log(
        db, admin, action="broadcast.send", target_type="user",
        detail=f"{data.audience}{f'={data.role}' if data.role else ''}: "
               f"{len(recipients)} người nhận, email={data.send_email}",
        commit=False,
    )
    db.commit()

    return BroadcastResult(
        recipients=len(recipients),
        notifications_created=notifications,
        emails_queued=emails,
    )


# --- UC-80 hàng đợi email ----------------------------------------------------

def list_emails(
    db: Session,
    *,
    email_status: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> EmailQueueListResponse:
    """UC-80 bước 1 — danh sách email, lọc theo trạng thái + đếm theo trạng thái."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = [EmailQueue.status == email_status] if email_status else []
    total = db.execute(select(func.count()).select_from(EmailQueue).where(*filters)).scalar_one()

    counts = {
        row_status: count
        for row_status, count in db.execute(
            select(EmailQueue.status, func.count(EmailQueue.id)).group_by(EmailQueue.status)
        ).all()
    }

    rows = db.execute(
        select(EmailQueue)
        .where(*filters)
        .order_by(EmailQueue.created_at.desc(), EmailQueue.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return EmailQueueListResponse(
        items=[EmailQueueRow.model_validate(r, from_attributes=True) for r in rows],
        total=total, page=page, page_size=page_size, counts=counts,
    )


def _get_email(db: Session, email_id: int) -> EmailQueue:
    email = db.get(EmailQueue, email_id)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy email"
        )
    return email


def retry_email(db: Session, admin: User, email_id: int) -> EmailQueueRow:
    """UC-80 bước 2 — đưa email thất bại về hàng đợi để worker gửi lại ngay."""
    email = _get_email(db, email_id)
    if email.status == email_service.STATUS_SENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email này đã gửi thành công"
        )

    email.status = email_service.STATUS_PENDING
    email.attempts = 0
    email.last_error = None
    email.scheduled_at = datetime.now(timezone.utc)

    audit_service.log(
        db, admin, action="email.retry", target_type="email",
        target_id=email.id, detail=email.to_email, commit=False,
    )
    db.commit()
    db.refresh(email)
    return EmailQueueRow.model_validate(email, from_attributes=True)


def delete_email(db: Session, admin: User, email_id: int) -> None:
    """UC-80 bước 2 — xóa hẳn một email khỏi hàng đợi."""
    email = _get_email(db, email_id)
    audit_service.log(
        db, admin, action="email.delete", target_type="email",
        target_id=email.id, detail=email.to_email, commit=False,
    )
    db.delete(email)
    db.commit()
