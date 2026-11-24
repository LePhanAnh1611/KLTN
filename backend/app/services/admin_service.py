"""UC-72 dashboard tổng quan · UC-73 quản lý người dùng (Admin).

Mọi thao tác thay đổi đều ghi AUDIT_LOG (UC-83).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.post import Post
from app.models.report import Report
from app.models.session import StudySession
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.admin import (
    AdminOverview,
    AdminUserListResponse,
    AdminUserRow,
    AdminWordSetListResponse,
    AdminWordSetRow,
    UserActiveUpdate,
    UserRoleUpdate,
    WordSetAdminUpdate,
)
from app.services import audit_service

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAU_DAYS = 30


def _count(db: Session, model, *filters) -> int:
    return db.execute(select(func.count()).select_from(model).where(*filters)).scalar_one()


def _active_learners_since(db: Session, since: datetime) -> int:
    return db.execute(
        select(func.count(func.distinct(StudySession.user_id)))
        .where(StudySession.status == "completed", StudySession.ended_at >= since)
    ).scalar_one()


def get_overview(db: Session) -> AdminOverview:
    """UC-72 — tổng hợp chỉ số bằng aggregation (E1: hệ thống trống -> toàn số 0)."""
    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    return AdminOverview(
        total_users=_count(db, User),
        active_users=_count(db, User, User.is_active.is_(True)),
        dau=_active_learners_since(db, day_start),
        mau=_active_learners_since(db, now - timedelta(days=MAU_DAYS)),
        total_sessions=_count(db, StudySession),
        total_interactions=_count(db, Interaction),
        total_word_sets=_count(db, WordSet, WordSet.deleted_at.is_(None)),
        public_word_sets=_count(
            db, WordSet, WordSet.deleted_at.is_(None), WordSet.is_public.is_(True)
        ),
        total_items=_count(db, Item, Item.deleted_at.is_(None)),
        total_posts=_count(db, Post, Post.deleted_at.is_(None)),
        pending_reports=_count(db, Report, Report.status == "pending"),
    )


def list_users(
    db: Session,
    viewer: User,
    *,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AdminUserListResponse:
    """UC-73 bước 1 — tìm/lọc người dùng theo email/tên/vai trò/trạng thái."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = []
    if search:
        pattern = f"%{search}%"
        filters.append(User.email.ilike(pattern) | User.display_name.ilike(pattern))
    if role:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    total = db.execute(select(func.count()).select_from(User).where(*filters)).scalar_one()
    rows = db.execute(
        select(User, func.coalesce(UserProgress.xp, 0))
        .outerjoin(UserProgress, UserProgress.user_id == User.id)
        .where(*filters)
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AdminUserListResponse(
        items=[
            AdminUserRow(
                id=u.id, email=u.email, display_name=u.display_name, role=u.role,
                is_active=u.is_active, created_at=u.created_at, xp=int(xp),
                is_me=u.id == viewer.id,
            )
            for u, xp in rows
        ],
        total=total, page=page, page_size=page_size,
    )


def _get_target(db: Session, admin: User, user_id: int) -> User:
    """E1 — chặn Admin tự khóa / tự hạ quyền chính mình."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự thay đổi quyền hoặc trạng thái của chính mình",
        )
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng"
        )
    return target


def set_user_role(db: Session, admin: User, user_id: int, data: UserRoleUpdate) -> AdminUserRow:
    """UC-73 — đổi vai trò người dùng (RBAC)."""
    target = _get_target(db, admin, user_id)
    old_role = target.role
    target.role = data.role

    audit_service.log(
        db, admin, action="user.role_change", target_type="user", target_id=target.id,
        detail=f"{old_role} -> {data.role}", commit=False,
    )
    db.commit()
    db.refresh(target)
    return _to_row(db, target, admin)


def set_user_active(db: Session, admin: User, user_id: int, data: UserActiveUpdate) -> AdminUserRow:
    """UC-73 — khóa / mở khóa tài khoản."""
    target = _get_target(db, admin, user_id)
    target.is_active = data.is_active

    audit_service.log(
        db, admin,
        action="user.unlock" if data.is_active else "user.lock",
        target_type="user", target_id=target.id, detail=data.reason, commit=False,
    )
    db.commit()
    db.refresh(target)
    return _to_row(db, target, admin)


def list_word_sets(
    db: Session,
    *,
    search: str | None = None,
    is_public: bool | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> AdminWordSetListResponse:
    """UC-75 bước 1 — kho bộ từ (chỉ bộ chưa xóa mềm), lọc theo tên/trạng thái."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = [WordSet.deleted_at.is_(None)]
    if search:
        filters.append(WordSet.name.ilike(f"%{search}%"))
    if is_public is not None:
        filters.append(WordSet.is_public.is_(is_public))

    total = db.execute(select(func.count()).select_from(WordSet).where(*filters)).scalar_one()

    item_counts = (
        select(Item.word_set_id.label("ws_id"), func.count(Item.id).label("n"))
        .where(Item.deleted_at.is_(None))
        .group_by(Item.word_set_id)
        .subquery()
    )
    rows = db.execute(
        select(WordSet, User.display_name, func.coalesce(item_counts.c.n, 0))
        .join(User, User.id == WordSet.owner_id)
        .outerjoin(item_counts, item_counts.c.ws_id == WordSet.id)
        .where(*filters)
        .order_by(WordSet.created_at.desc(), WordSet.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AdminWordSetListResponse(
        items=[_to_word_set_row(ws, owner_name, int(n)) for ws, owner_name, n in rows],
        total=total, page=page, page_size=page_size,
    )


def _get_word_set(db: Session, word_set_id: int) -> WordSet:
    word_set = db.get(WordSet, word_set_id)
    if word_set is None or word_set.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bộ từ vựng"
        )
    return word_set


def update_word_set(
    db: Session, admin: User, word_set_id: int, data: WordSetAdminUpdate
) -> AdminWordSetRow:
    """UC-75 bước 2 — gắn/bỏ nổi bật (UC-22) hoặc gỡ công khai."""
    word_set = _get_word_set(db, word_set_id)

    changes: list[str] = []
    if data.is_featured is not None and data.is_featured != word_set.is_featured:
        word_set.is_featured = data.is_featured
        changes.append(f"is_featured={data.is_featured}")
    if data.is_public is not None and data.is_public != word_set.is_public:
        word_set.is_public = data.is_public
        changes.append(f"is_public={data.is_public}")

    if changes:
        audit_service.log(
            db, admin, action="word_set.update", target_type="word_set",
            target_id=word_set.id, detail=", ".join(changes), commit=False,
        )
    db.commit()
    db.refresh(word_set)
    return _word_set_row_from_db(db, word_set)


def delete_word_set(db: Session, admin: User, word_set_id: int) -> None:
    """UC-75 E1 — bộ đang được dùng thì xóa MỀM (Q6) để giữ toàn vẹn INTERACTION."""
    word_set = _get_word_set(db, word_set_id)
    word_set.deleted_at = datetime.now(timezone.utc)
    audit_service.log(
        db, admin, action="word_set.delete", target_type="word_set",
        target_id=word_set.id, detail=word_set.name, commit=False,
    )
    db.commit()


def _to_word_set_row(ws: WordSet, owner_name: str, item_count: int) -> AdminWordSetRow:
    return AdminWordSetRow(
        id=ws.id, name=ws.name, owner_id=ws.owner_id, owner_name=owner_name,
        category=ws.category, difficulty=ws.difficulty, is_public=ws.is_public,
        is_featured=ws.is_featured, download_count=ws.download_count,
        item_count=item_count, created_at=ws.created_at,
    )


def _word_set_row_from_db(db: Session, ws: WordSet) -> AdminWordSetRow:
    owner_name = db.execute(
        select(User.display_name).where(User.id == ws.owner_id)
    ).scalar_one()
    item_count = db.execute(
        select(func.count()).select_from(Item)
        .where(Item.word_set_id == ws.id, Item.deleted_at.is_(None))
    ).scalar_one()
    return _to_word_set_row(ws, owner_name, item_count)


def _to_row(db: Session, user: User, viewer: User) -> AdminUserRow:
    xp = db.execute(
        select(func.coalesce(UserProgress.xp, 0)).where(UserProgress.user_id == user.id)
    ).scalar() or 0
    return AdminUserRow(
        id=user.id, email=user.email, display_name=user.display_name, role=user.role,
        is_active=user.is_active, created_at=user.created_at, xp=int(xp),
        is_me=user.id == viewer.id,
    )
