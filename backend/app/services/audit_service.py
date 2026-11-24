"""UC-83 — ghi & tra cứu nhật ký thao tác quản trị.

Mọi hành động Admin thay đổi dữ liệu (UC-73/75/77/78/81) đều gọi `log()`.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import AuditLogEntry, AuditLogListResponse

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def log(
    db: Session,
    actor: User,
    *,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: str | None = None,
    commit: bool = True,
) -> AuditLog:
    """Ghi một mục nhật ký. `commit=False` để gộp vào transaction của service gọi."""
    entry = AuditLog(
        actor_id=actor.id, action=action,
        target_type=target_type, target_id=target_id, detail=detail,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def list_logs(
    db: Session,
    *,
    action: str | None = None,
    actor_id: int | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AuditLogListResponse:
    """UC-83 — truy vấn nhật ký, lọc theo thao tác/người thực hiện."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)

    total = db.execute(select(func.count()).select_from(AuditLog).where(*filters)).scalar_one()

    actor = aliased(User)
    rows = db.execute(
        select(AuditLog, actor.display_name)
        .outerjoin(actor, actor.id == AuditLog.actor_id)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AuditLogListResponse(
        items=[
            AuditLogEntry(
                id=entry.id, action=entry.action, target_type=entry.target_type,
                target_id=entry.target_id, detail=entry.detail,
                actor_id=entry.actor_id, actor_name=actor_name,
                created_at=entry.created_at,
            )
            for entry, actor_name in rows
        ],
        total=total, page=page, page_size=page_size,
    )
