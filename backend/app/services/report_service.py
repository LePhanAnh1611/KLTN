"""UC-24 (bộ từ) & UC-53 (bài viết) — tạo báo cáo vi phạm cho hàng đợi Admin.

Viết generic theo `target_type` để dùng chung cho cả hai UC. Việc Admin xử lý
hàng đợi là UC-78 (M7) — ở đây chỉ ghi nhận trạng thái 'pending'.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportRequest, ReportResponse

TARGET_WORD_SET = "word_set"
TARGET_POST = "post"

PENDING = "pending"


def create_report(
    db: Session,
    user: User,
    *,
    target_type: str,
    target_id: int,
    data: ReportRequest,
) -> ReportResponse:
    """Tạo REPORT chờ xử lý. E1: cùng người + cùng đối tượng còn 'pending' -> gộp."""
    existing = db.execute(
        select(Report).where(
            Report.reporter_id == user.id,
            Report.target_type == target_type,
            Report.target_id == target_id,
            Report.status == PENDING,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ReportResponse.model_validate(existing).model_copy(update={"merged": True})

    report = Report(
        reporter_id=user.id,
        target_type=target_type,
        target_id=target_id,
        reason=data.reason,
        description=data.description,
        status=PENDING,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return ReportResponse.model_validate(report)
