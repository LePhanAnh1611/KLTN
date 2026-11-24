"""UC-62 gửi email từ hàng đợi · UC-63 nhắc ôn tập / streak."""
from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.email_queue import EmailQueue
from app.models.item import Item
from app.models.notification import Notification
from app.models.review_schedule import ReviewSchedule
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import email_service, reminder_service
from app.services.auth_service import register_user

#: UC-09/UC-63 — job nay chay MOI GIO va chi nhac dung gio cua tung nguoi hoc,
#: nen test phai noi ro "bay gio la may gio" thay vi mac dinh nhu truoc.


def _vn_hour_today(hour: int) -> datetime:
    """Thời điểm UTC ứng với `hour` giờ Việt Nam của NGÀY HÔM NAY.

    Phải bám theo hôm nay chứ không đóng đinh một ngày cụ thể: các bản ghi trong
    test dựng bằng `datetime.now()`, nên một mốc cứng sẽ lùi dần vào quá khứ và
    test hỏng vào một ngày đẹp trời — đúng lỗi bản đầu của test này mắc phải.
    """
    from zoneinfo import ZoneInfo

    vn = ZoneInfo("Asia/Ho_Chi_Minh")
    today = datetime.now(timezone.utc).astimezone(vn).date()
    return datetime(today.year, today.month, today.day, hour, tzinfo=vn).astimezone(timezone.utc)


def _at_reminder_hour(db_session, **kwargs):
    """Chạy job đúng vào giờ nhắc mặc định của người học (20:00 giờ địa phương)."""
    return reminder_service.run_reminders(
        db_session, now=_vn_hour_today(reminder_service.DEFAULT_REMINDER_HOUR), **kwargs
    )


def _user(db_session, email, role="learner"):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    if role != "learner":
        u.role = role
        db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _clear_verification_emails(db_session):
    """Đăng ký giờ tự xếp email xác thực (UC-03). Các test dưới đây kiểm tra cơ
    chế hàng đợi/nhắc ôn nên dọn email đó đi để số liệu không lẫn."""
    for row in db_session.execute(
        select(EmailQueue).where(EmailQueue.template == "email_verify")
    ).scalars().all():
        db_session.delete(row)
    db_session.commit()


def _due_item(db_session, user_id, days_overdue=1):
    ws = WordSet(owner_id=user_id, name="Bộ ôn")
    db_session.add(ws)
    db_session.flush()
    item = Item(word_set_id=ws.id, word="apple", meaning="quả táo")
    db_session.add(item)
    db_session.flush()
    db_session.add(ReviewSchedule(
        user_id=user_id, item_id=item.id,
        next_review_at=datetime.now(timezone.utc) - timedelta(days=days_overdue),
    ))
    db_session.commit()
    return item


# --- UC-62 -------------------------------------------------------------------

def test_process_queue_sends_pending(db_session):
    user, _ = _user(db_session, "em.a@example.com")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, user, to_email=user.email, subject="Chào", body="Nội dung")

    result = email_service.process_queue(db_session)

    assert result == {"sent": 1, "failed": 0, "retry": 0}
    row = db_session.execute(select(EmailQueue)).scalars().one()
    assert row.status == "sent" and row.sent_at is not None and row.attempts == 1


def test_process_queue_retries_then_fails(db_session, monkeypatch):
    """E1 — gửi lỗi thì lùi lịch & tăng attempts; quá ngưỡng -> 'failed'."""
    user, _ = _user(db_session, "em.b@example.com")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, user, to_email=user.email, subject="Lỗi", body="x")

    def _boom(_email):
        raise RuntimeError("SMTP sập")

    monkeypatch.setattr(email_service, "_send_now", _boom)

    first = email_service.process_queue(db_session)
    assert first["retry"] == 1
    row = db_session.execute(select(EmailQueue)).scalars().one()
    assert row.status == "pending" and row.attempts == 1
    assert row.scheduled_at > datetime.now(timezone.utc)   # backoff
    assert "SMTP sập" in row.last_error

    # tới lịch retry: đủ MAX_ATTEMPTS thì chuyển 'failed'
    for _ in range(email_service.MAX_ATTEMPTS - 1):
        row.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()
        email_service.process_queue(db_session)

    db_session.refresh(row)
    assert row.status == "failed" and row.attempts == email_service.MAX_ATTEMPTS


def test_backoff_holds_email_until_scheduled(db_session, monkeypatch):
    """Email đang chờ retry không bị lấy ra trước hạn."""
    user, _ = _user(db_session, "em.c@example.com")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, user, to_email=user.email, subject="Chờ", body="x")
    monkeypatch.setattr(email_service, "_send_now", lambda _e: (_ for _ in ()).throw(RuntimeError("lỗi")))
    email_service.process_queue(db_session)

    monkeypatch.undo()
    assert email_service.process_queue(db_session) == {"sent": 0, "failed": 0, "retry": 0}


# --- UC-63 -------------------------------------------------------------------

def test_reminder_creates_notification_and_email(db_session):
    user, _ = _user(db_session, "rm.a@example.com")
    _clear_verification_emails(db_session)
    _due_item(db_session, user.id)

    result = _at_reminder_hour(db_session)

    assert result["review_due"] == 1
    notification = db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    ).scalars().one()
    assert notification.type == "review_due" and notification.link == "/reviews"
    assert "1 từ cần ôn" in notification.title

    email = db_session.execute(select(EmailQueue)).scalars().one()
    assert email.to_email == user.email and email.template == "review_due"


def test_reminder_not_repeated_same_day(db_session):
    """E1 — đã nhắc trong ngày thì lần quét sau bỏ qua."""
    user, _ = _user(db_session, "rm.b@example.com")
    _due_item(db_session, user.id)

    assert _at_reminder_hour(db_session)["review_due"] == 1
    assert _at_reminder_hour(db_session)["review_due"] == 0

    rows = db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    ).scalars().all()
    assert len(rows) == 1


def test_reminder_skips_user_without_due_items(db_session):
    _user(db_session, "rm.c@example.com")
    assert _at_reminder_hour(db_session) == {"review_due": 0, "streak_risk": 0}


def test_reminder_respects_notification_preference(db_session):
    """Tắt nhắc ôn (UC-60) -> không sinh thông báo lẫn email."""
    from app.models.user_settings import UserSettings

    user, _ = _user(db_session, "rm.d@example.com")
    _clear_verification_emails(db_session)
    _due_item(db_session, user.id)
    settings_row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    settings_row.notify_review = False
    db_session.commit()

    assert _at_reminder_hour(db_session)["review_due"] == 0
    assert db_session.execute(select(EmailQueue)).scalars().all() == []


def test_streak_risk_reminder(db_session):
    """Đang có streak nhưng hôm nay chưa học -> cảnh báo sắp đứt chuỗi."""
    user, _ = _user(db_session, "rm.e@example.com")
    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one()
    progress.streak_count = 5
    # Sau UC-88, "hôm qua" tính theo múi giờ NGƯỜI HỌC chứ không theo UTC — hai
    # thứ lệch nhau đúng trong khung 00:00–07:00 giờ Việt.
    progress.last_activity_date = _vn_hour_today(12).astimezone(
        ZoneInfo("Asia/Ho_Chi_Minh")).date() - timedelta(days=1)
    db_session.commit()

    assert _at_reminder_hour(db_session)["streak_risk"] == 1
    notification = db_session.execute(
        select(Notification).where(Notification.type == "streak_risk")
    ).scalars().one()
    assert "Chuỗi 5 ngày" in notification.title


def test_nhac_dung_gio_nguoi_hoc_da_dat(db_session):
    """UC-09 — `reminder_time` phải có hiệu lực thật.

    Trước đây trường này được lưu rồi bỏ đó: job chạy một lần/ngày ở một giờ
    UTC cố định cho tất cả mọi người. Người học đặt 20:00 vẫn bị nhắc lúc 3 giờ
    sáng, hoặc không được nhắc đúng lúc mình muốn.
    """
    from datetime import time as time_

    from app.models.user_settings import UserSettings

    user, _ = _user(db_session, "rm.hour@example.com")
    _clear_verification_emails(db_session)
    _due_item(db_session, user.id)

    row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    row.reminder_time = time_(6, 0)          # 06:00 giờ Việt Nam
    row.timezone = "Asia/Ho_Chi_Minh"
    db_session.commit()

    # 20:00 giờ VN — giờ mặc định, nhưng người này đã đổi sang 06:00 -> im lặng
    assert reminder_service.run_reminders(
        db_session, now=_vn_hour_today(20))["review_due"] == 0

    # đúng 06:00 giờ VN -> phải nhắc
    sau_gio_nhac = _vn_hour_today(6)
    assert reminder_service.run_reminders(db_session, now=sau_gio_nhac)["review_due"] == 1

    # và không nhắc lại lần hai trong cùng ngày của chính người đó
    assert reminder_service.run_reminders(db_session, now=sau_gio_nhac)["review_due"] == 0


def test_mui_gio_khac_nhau_thi_gio_nhac_khac_nhau(db_session):
    """Cùng đặt 20:00 nhưng ở hai múi giờ thì hai thời điểm UTC khác nhau."""
    from datetime import time as time_

    from app.models.user_settings import UserSettings

    vn, _ = _user(db_session, "rm.vn@example.com")
    jp, _ = _user(db_session, "rm.jp@example.com")
    _clear_verification_emails(db_session)
    _due_item(db_session, vn.id)
    _due_item(db_session, jp.id)

    for user, tz in ((vn, "Asia/Ho_Chi_Minh"), (jp, "Asia/Tokyo")):
        row = db_session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        ).scalar_one()
        row.reminder_time = time_(20, 0)
        row.timezone = tz
        db_session.commit()

    # 20:00 giờ Tokyo (sớm hơn Việt Nam 2 tiếng) -> chỉ người Nhật được nhắc
    tokyo_20h = _vn_hour_today(18)      # 18:00 VN = 20:00 Tokyo
    assert reminder_service.run_reminders(db_session, now=tokyo_20h)["review_due"] == 1
    # rồi tới 20:00 giờ Việt Nam -> đến lượt người Việt
    assert reminder_service.run_reminders(db_session, now=_vn_hour_today(20))["review_due"] == 1


# --- endpoint chạy tay -------------------------------------------------------

def test_job_endpoints_admin_only(client, db_session):
    _, learner = _user(db_session, "jb.a@example.com")
    admin, admin_headers = _user(db_session, "jb.b@example.com", role="admin")
    _clear_verification_emails(db_session)
    _due_item(db_session, admin.id)

    assert client.post("/api/v1/admin/jobs/run-reminders", headers=learner).status_code == 403
    assert client.post("/api/v1/admin/jobs/send-emails", headers=learner).status_code == 403

    assert client.post("/api/v1/admin/jobs/run-reminders", headers=admin_headers).json()["review_due"] == 1
    assert client.post("/api/v1/admin/jobs/send-emails", headers=admin_headers).json()["sent"] == 1
