"""UC-63 — nhắc ôn tập & cảnh báo streak sắp đứt.

Tác vụ quét người dùng có item đến hạn (BR-02) hoặc streak nguy cơ mất, rồi gọi
UC-61 sinh thông báo in-app + email. E1: đã nhắc trong ngày thì bỏ qua — kiểm tra
bằng chính NOTIFICATION đã tạo hôm nay (không cần bảng "đã nhắc" riêng).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import day_bounds_in, resolve_zone
from app.models.notification import Notification
from app.models.review_schedule import ReviewSchedule
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.services import email_service, notification_service

REVIEW_LINK = "/reviews"

#: Giờ nhắc mặc định (giờ ĐỊA PHƯƠNG của người học) khi họ chưa tự đặt ở UC-09.
DEFAULT_REMINDER_HOUR = 20


def _already_notified_today(db: Session, user_id: int, type_: str, day_start: datetime) -> bool:
    """E1 — chống nhắc trùng trong ngày (ngày tính theo múi giờ người học)."""
    return db.execute(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == type_,
            Notification.created_at >= day_start,
        ).limit(1)
    ).first() is not None


def _is_reminder_hour(
    settings_row: UserSettings | None, now: datetime
) -> tuple[bool, datetime, date]:
    """Đã tới GIỜ NHẮC của người học này chưa, và mốc đầu ngày của họ là lúc nào.

    UC-09 cho người học đặt "giờ nhắc" và trước đây hệ thống **lưu rồi bỏ đó**:
    job chạy một lần mỗi ngày ở một giờ UTC cố định cho tất cả mọi người, không
    ai đọc `reminder_time`. Người học đặt 20:00 thì vẫn bị nhắc lúc 3 giờ sáng.

    Nay job chạy mỗi giờ, và mỗi người chỉ được nhắc khi giờ địa phương của họ
    khớp giờ họ đã chọn. Chưa chọn thì dùng mặc định 20:00 giờ địa phương.
    """
    zone = resolve_zone(settings_row.timezone if settings_row else None)
    local_now = now.astimezone(zone)
    wanted = (
        settings_row.reminder_time.hour
        if settings_row is not None and settings_row.reminder_time is not None
        else DEFAULT_REMINDER_HOUR
    )
    day_start, _ = day_bounds_in(zone, now)
    # Trả luôn NGÀY ĐỊA PHƯƠNG: `day_start.date()` là ngày theo UTC của cái mốc
    # đó (giờ Việt thì mốc đầu ngày rơi vào 17:00 hôm trước), lấy nhầm là lệch
    # đúng một ngày.
    return local_now.hour == wanted, day_start, local_now.date()


def _due_counts(db: Session, now: datetime) -> dict[int, int]:
    """{user_id: số item đến hạn ôn}."""
    rows = db.execute(
        select(ReviewSchedule.user_id, func.count(ReviewSchedule.id))
        .where(ReviewSchedule.next_review_at <= now, ReviewSchedule.is_paused.is_(False))
        .group_by(ReviewSchedule.user_id)
    ).all()
    return {user_id: count for user_id, count in rows}


def run_reminders(
    db: Session, *, now: datetime | None = None, force: bool = False
) -> dict[str, int]:
    """Quét & gửi nhắc. Trả {'review_due': n, 'streak_risk': n} cho job/endpoint.

    `force=True` bỏ qua cổng "đúng giờ nhắc" — dành cho nút chạy tay của Admin
    (UC-80): bấm "chạy ngay" mà không gửi gì thì nút đó vô nghĩa. Chống nhắc
    trùng trong ngày vẫn giữ nguyên.

    - review_due: có item đến hạn ôn hôm nay.
    - streak_risk: đang có streak nhưng hôm nay chưa học (lần hoạt động cuối là hôm qua).
    """
    now = now or datetime.now(timezone.utc)
    result = {"review_due": 0, "streak_risk": 0}

    due = _due_counts(db, now)
    progress_rows = {
        row.user_id: row for row in db.execute(select(UserProgress)).scalars().all()
    }

    settings_rows = {
        row.user_id: row for row in db.execute(select(UserSettings)).scalars().all()
    }

    users = db.execute(select(User).where(User.is_active.is_(True))).scalars().all()
    for user in users:
        # UC-09: chỉ nhắc đúng giờ NGƯỜI HỌC đã chọn, theo múi giờ của họ (UC-88).
        at_hour, day_start, user_today = _is_reminder_hour(settings_rows.get(user.id), now)
        if not (at_hour or force):
            continue

        due_count = due.get(user.id, 0)
        if due_count and not _already_notified_today(db, user.id, "review_due", day_start):
            created = notification_service.notify(
                db, user.id, type_="review_due",
                title=f"Bạn có {due_count} từ cần ôn hôm nay",
                body="Ôn đúng lịch giúp giữ mastery và nối dài streak.",
                link=REVIEW_LINK, commit=False,
            )
            if created is not None:
                email_service.enqueue(
                    db, user,
                    to_email=user.email,
                    subject=f"[LearningHub] {due_count} từ đang chờ bạn ôn",
                    body=(
                        f"Chào {user.display_name},\n\n"
                        f"Hôm nay bạn có {due_count} từ đến hạn ôn tập. "
                        f"Đăng nhập và vào mục Lịch ôn để giữ tiến độ nhé.\n"
                    ),
                    template="review_due", commit=False,
                )
                result["review_due"] += 1

        # "Hôm qua" cũng theo lịch của chính người học (UC-88), không thì cảnh
        # báo đứt chuỗi bắn sai ngày với người ở múi giờ khác.
        progress = progress_rows.get(user.id)
        at_risk = (
            progress is not None
            and progress.streak_count > 0
            and progress.last_activity_date == user_today - timedelta(days=1)
        )
        if at_risk and not _already_notified_today(db, user.id, "streak_risk", day_start):
            created = notification_service.notify(
                db, user.id, type_="streak_risk",
                title=f"Chuỗi {progress.streak_count} ngày sắp đứt",
                body="Học một phiên ngắn hôm nay để giữ chuỗi.",
                link=REVIEW_LINK, commit=False,
            )
            if created is not None:
                result["streak_risk"] += 1

    db.commit()
    return result
