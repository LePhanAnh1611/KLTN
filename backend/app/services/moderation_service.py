"""UC-77 kiểm duyệt cộng đồng · UC-78 xử lý báo cáo (Admin).

Khép vòng với UC-49 (bài chờ duyệt khi bật `require_post_approval` ở UC-81) và
UC-24/53 (báo cáo do người dùng gửi). Mọi quyết định đều ghi AUDIT_LOG (UC-83)
và báo cho tác giả bằng thông báo in-app (UC-61).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.admin import (
    ModerationDecision,
    ModerationPost,
    ModerationPostListResponse,
    ReportDecision,
    ReportListResponse,
    ReportRow,
)
from app.services import audit_service, notification_service
from app.services.community_service import STATUS_APPROVED, STATUS_PENDING
from app.services.report_service import PENDING, TARGET_POST, TARGET_WORD_SET

STATUS_REJECTED = "rejected"
REPORT_RESOLVED = "resolved"
REPORT_DISMISSED = "dismissed"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

PREVIEW_CHARS = 120


# --- UC-77 kiểm duyệt bài ----------------------------------------------------

def list_posts_for_moderation(
    db: Session,
    *,
    post_status: str = STATUS_PENDING,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ModerationPostListResponse:
    """UC-77 bước 1 — bài theo trạng thái (mặc định 'chờ duyệt')."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = [Post.deleted_at.is_(None), Post.status == post_status]
    total = db.execute(select(func.count()).select_from(Post).where(*filters)).scalar_one()
    rows = db.execute(
        select(Post, User.display_name)
        .join(User, User.id == Post.author_id)
        .where(*filters)
        .order_by(Post.created_at, Post.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ModerationPostListResponse(
        items=[
            ModerationPost(
                id=p.id, post_type=p.post_type, content=p.content, image_url=p.image_url,
                status=p.status, created_at=p.created_at,
                author_id=p.author_id, author_name=author_name,
            )
            for p, author_name in rows
        ],
        total=total, page=page, page_size=page_size,
    )


def _get_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết"
        )
    return post


def moderate_post(
    db: Session, admin: User, post_id: int, data: ModerationDecision
) -> ModerationPost:
    """UC-77 bước 2/3 — duyệt (hiển thị) / từ chối / gỡ; ghi log + báo tác giả."""
    post = _get_post(db, post_id)

    if data.decision == "approve":
        post.status = STATUS_APPROVED
        title = "Bài viết của bạn đã được duyệt"
    elif data.decision == "reject":
        post.status = STATUS_REJECTED
        title = "Bài viết của bạn không được duyệt"
    else:  # remove — gỡ bài đã hiển thị (xóa mềm, Q6)
        post.deleted_at = datetime.now(timezone.utc)
        title = "Bài viết của bạn đã bị gỡ"

    notification_service.notify(
        db, post.author_id, type_="system", title=title,
        body=data.reason, link="/community", commit=False,
    )
    audit_service.log(
        db, admin, action=f"post.{data.decision}", target_type="post",
        target_id=post.id, detail=data.reason, commit=False,
    )
    db.commit()
    db.refresh(post)

    author_name = db.execute(
        select(User.display_name).where(User.id == post.author_id)
    ).scalar_one()
    return ModerationPost(
        id=post.id, post_type=post.post_type, content=post.content,
        image_url=post.image_url, status=post.status, created_at=post.created_at,
        author_id=post.author_id, author_name=author_name,
    )


# --- UC-78 xử lý báo cáo -----------------------------------------------------

def _target_info(db: Session, report: Report) -> tuple[str | None, bool]:
    """(trích dẫn đối tượng bị báo cáo, đối tượng còn hiển thị công khai không).

    Bộ từ bị gỡ = hết công khai (không xóa cứng, giữ thư viện người đã tải).
    """
    if report.target_type == TARGET_WORD_SET:
        word_set = db.get(WordSet, report.target_id)
        if word_set is None:
            return None, False
        visible = word_set.deleted_at is None and word_set.is_public
        return word_set.name, visible

    post = db.get(Post, report.target_id)
    if post is None or post.deleted_at is not None:
        return (post.content[:PREVIEW_CHARS] if post else None), False
    return post.content[:PREVIEW_CHARS], True


def list_reports(
    db: Session,
    *,
    report_status: str = PENDING,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ReportListResponse:
    """UC-78 bước 1 — hàng đợi báo cáo (mặc định 'chờ xử lý')."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = [Report.status == report_status] if report_status else []
    total = db.execute(select(func.count()).select_from(Report).where(*filters)).scalar_one()

    reporter = aliased(User)
    rows = db.execute(
        select(Report, reporter.display_name)
        .join(reporter, reporter.id == Report.reporter_id)
        .where(*filters)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for report, reporter_name in rows:
        preview, exists = _target_info(db, report)
        items.append(ReportRow(
            id=report.id, target_type=report.target_type, target_id=report.target_id,
            reason=report.reason, description=report.description, status=report.status,
            created_at=report.created_at, resolved_at=report.resolved_at,
            reporter_id=report.reporter_id, reporter_name=reporter_name,
            target_preview=preview, target_exists=exists,
        ))

    return ReportListResponse(items=items, total=total, page=page, page_size=page_size)


def resolve_report(
    db: Session, admin: User, report_id: int, data: ReportDecision
) -> ReportRow:
    """UC-78 bước 2/3 — bỏ qua, hoặc gỡ nội dung bị báo cáo rồi đóng báo cáo.

    Gỡ nội dung = xóa mềm bài (Q6) / gỡ công khai bộ từ — không xóa cứng để giữ
    toàn vẹn INTERACTION.
    """
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy báo cáo"
        )
    if report.status != PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Báo cáo này đã được xử lý"
        )

    if data.decision == "remove_content":
        if report.target_type == TARGET_POST:
            post = db.get(Post, report.target_id)
            if post is not None and post.deleted_at is None:
                post.deleted_at = datetime.now(timezone.utc)
                notification_service.notify(
                    db, post.author_id, type_="system",
                    title="Bài viết của bạn đã bị gỡ do vi phạm",
                    body=data.note, link="/community", commit=False,
                )
        else:
            word_set = db.get(WordSet, report.target_id)
            if word_set is not None and word_set.is_public:
                word_set.is_public = False
                word_set.is_featured = False
                notification_service.notify(
                    db, word_set.owner_id, type_="system",
                    title=f'Bộ từ "{word_set.name}" đã bị gỡ khỏi kho công khai',
                    body=data.note, link="/word-sets", commit=False,
                )
        report.status = REPORT_RESOLVED
    else:
        report.status = REPORT_DISMISSED

    report.resolved_at = datetime.now(timezone.utc)
    audit_service.log(
        db, admin, action=f"report.{data.decision}", target_type=report.target_type,
        target_id=report.target_id, detail=data.note, commit=False,
    )
    db.commit()
    db.refresh(report)

    reporter_name = db.execute(
        select(User.display_name).where(User.id == report.reporter_id)
    ).scalar_one()
    preview, exists = _target_info(db, report)
    return ReportRow(
        id=report.id, target_type=report.target_type, target_id=report.target_id,
        reason=report.reason, description=report.description, status=report.status,
        created_at=report.created_at, resolved_at=report.resolved_at,
        reporter_id=report.reporter_id, reporter_name=reporter_name,
        target_preview=preview, target_exists=exists,
    )
