"""Chạy tay các tác vụ nền UC-62 / UC-63 (bình thường do scheduler gọi).

Dùng khi demo hoặc khi tắt scheduler và cắm cron/Task Scheduler bên ngoài.
Cần quyền `admin.jobs` (UC-74).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.user import User
from app.services import email_service, reminder_service

router = APIRouter()


@router.post("/send-emails", response_model=dict)
def run_email_worker(
    _: User = Depends(require_permission("admin.jobs")),
    db: Session = Depends(get_db),
) -> dict:
    """UC-62 — đẩy một lô email trong hàng đợi."""
    return email_service.process_queue(db)


@router.post("/run-reminders", response_model=dict)
def run_reminders(
    _: User = Depends(require_permission("admin.jobs")),
    db: Session = Depends(get_db),
) -> dict:
    """UC-63 — quét & gửi nhắc ôn / cảnh báo streak."""
    # force=True: Admin bấm "chạy ngay" thì phải gửi ngay, không đợi tới giờ
    # nhắc của từng người (UC-09).
    return reminder_service.run_reminders(db, force=True)
