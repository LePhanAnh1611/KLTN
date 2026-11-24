"""UC-61 (phần email) xếp hàng · UC-62 gửi email từ hàng đợi.

Mặc định `settings.email_backend='log'`: email được "gửi" bằng cách ghi log —
đủ để demo trọn vòng mà không phụ thuộc dịch vụ ngoài. Đặt 'smtp' + biến môi
trường SMTP_* để gửi thật, phần còn lại (hàng đợi, retry, trạng thái) giữ nguyên.
Ở chế độ 'smtp' chỉ các loại trong `EMAIL_REAL_TEMPLATES` (mặc định: đặt lại mật
khẩu + xác thực email) đi ra ngoài; loại khác vẫn chỉ ghi log.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_queue import EmailQueue
from app.models.user import User

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"

MAX_ATTEMPTS = 3          # quá số lần này -> 'failed' (E1 UC-62)
BACKOFF_MINUTES = 5       # lần thử n sẽ lùi n * BACKOFF_MINUTES phút
BATCH_SIZE = 20


def enqueue(
    db: Session,
    user: User | None,
    *,
    to_email: str,
    subject: str,
    body: str,
    template: str | None = None,
    commit: bool = True,
) -> EmailQueue:
    """UC-61 bước 3 — đưa email vào hàng đợi ở trạng thái chờ gửi."""
    email = EmailQueue(
        user_id=user.id if user else None,
        to_email=to_email,
        subject=subject,
        body=body,
        template=template,
        status=STATUS_PENDING,
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(email)
    if commit:
        db.commit()
        db.refresh(email)
    else:
        db.flush()
    return email


def should_send_real(email: EmailQueue) -> bool:
    """Email này có đi ra SMTP thật không (xem `email_real_templates`)."""
    if settings.email_backend != "smtp":
        return False
    allowed = settings.email_real_template_set
    return "*" in allowed or (email.template or "") in allowed


def _send_now(email: EmailQueue) -> None:
    """Gửi thật qua backend đang cấu hình; ném exception nếu lỗi (để retry)."""
    if not should_send_real(email):
        logger.info(
            "[EMAIL:log] to=%s template=%s subject=%s",
            email.to_email, email.template, email.subject,
        )
        return

    message = EmailMessage()
    message["From"] = formataddr(("LearningHub", settings.email_from))
    message["To"] = email.to_email
    message["Subject"] = email.subject
    message.set_content(email.body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password or "")
        smtp.send_message(message)


def process_queue(db: Session, *, batch_size: int = BATCH_SIZE) -> dict[str, int]:
    """UC-62 — lấy một lô email chờ gửi, gửi, cập nhật trạng thái.

    E1: gửi lỗi -> tăng attempts + lùi lịch (backoff); quá MAX_ATTEMPTS -> 'failed'.
    Trả {'sent': n, 'failed': n, 'retry': n} để job/endpoint báo cáo lại.
    """
    now = datetime.now(timezone.utc)
    batch = db.execute(
        select(EmailQueue)
        .where(
            EmailQueue.status == STATUS_PENDING,
            or_(EmailQueue.scheduled_at.is_(None), EmailQueue.scheduled_at <= now),
        )
        .order_by(EmailQueue.id)
        .limit(batch_size)
    ).scalars().all()

    result = {"sent": 0, "failed": 0, "retry": 0}
    for email in batch:
        email.attempts += 1
        try:
            _send_now(email)
        except Exception as exc:  # noqa: BLE001 — mọi lỗi gửi đều cho retry
            email.last_error = str(exc)[:500]
            if email.attempts >= MAX_ATTEMPTS:
                email.status = STATUS_FAILED
                result["failed"] += 1
                logger.warning("Email %s thất bại sau %s lần thử", email.id, email.attempts)
            else:
                email.scheduled_at = now + timedelta(minutes=BACKOFF_MINUTES * email.attempts)
                result["retry"] += 1
        else:
            email.status = STATUS_SENT
            email.sent_at = now
            email.last_error = None
            result["sent"] += 1

    db.commit()
    return result
