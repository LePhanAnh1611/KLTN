"""Tác vụ nền cho UC-62 (đẩy hàng đợi email) và UC-63 (quét nhắc ôn).

Chạy bằng APScheduler ngay trong tiến trình FastAPI — đủ cho phạm vi khóa luận,
không cần Celery/broker. Tắt bằng `SCHEDULER_ENABLED=false` (test luôn tắt).
Mỗi job tự mở session riêng vì chạy ngoài vòng đời request.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import email_service, model_monitor_service, pilot_service, reminder_service

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_email_worker() -> dict[str, int]:
    """UC-62 — gửi một lô email đang chờ."""
    with SessionLocal() as db:
        result = email_service.process_queue(db)
    if any(result.values()):
        logger.info("Email worker: %s", result)
    return result


def run_reminder_job() -> dict[str, int]:
    """UC-63 — quét người dùng cần nhắc ôn / cảnh báo streak."""
    with SessionLocal() as db:
        result = reminder_service.run_reminders(db)
    logger.info("Reminder job: %s", result)
    return result


def run_pilot_nightly() -> None:
    """Pilot — mỗi tối: chụp chỉ số sức khỏe mô hình (UC-70) + gửi email báo cáo."""
    with SessionLocal() as db:
        try:
            model_monitor_service.record_snapshot(db)
        except Exception:
            db.rollback()
            logger.exception("Pilot: không chụp được model_metrics")
        report = pilot_service.send_report(db)
    logger.info("Pilot report: %s người hôm nay, ready=%s", report.active_today, report.ready)


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled or _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_email_worker, "interval",
        seconds=settings.email_worker_interval_seconds, id="email_worker",
    )
    # Chạy MỖI GIỜ, không phải một lần/ngày: giờ nhắc nay là của TỪNG người học
    # (UC-09 + UC-88), nên job phải thức dậy đủ thường xuyên để bắt được mọi
    # múi giờ. Bên trong vẫn chống nhắc trùng theo ngày của chính người đó.
    _scheduler.add_job(run_reminder_job, "cron", minute=0, id="reminder_job")
    _scheduler.add_job(
        run_pilot_nightly, "cron", hour=settings.pilot_report_hour, minute=0,
        timezone=settings.pilot_timezone, id="pilot_nightly",
    )
    _scheduler.start()
    logger.info("Scheduler đã chạy (email worker + reminder job)")
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
