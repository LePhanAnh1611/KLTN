"""UC-82 broadcast · UC-80 quản lý hàng đợi email (Admin)."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.email_queue import EmailQueue
from app.models.user_settings import UserSettings
from app.schemas.auth import RegisterRequest
from app.services import email_service
from app.services.auth_service import register_user


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


# --- UC-82 -------------------------------------------------------------------

def test_broadcast_to_all_creates_notifications(client, db_session):
    admin, admin_headers = _user(db_session, "bc.a1@example.com", role="admin")
    _, learner_headers = _user(db_session, "bc.a2@example.com")

    r = client.post("/api/v1/admin/broadcast", headers=admin_headers, json={
        "title": "Bảo trì hệ thống", "body": "22h tối nay", "link": "/",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["recipients"] == 2 and body["notifications_created"] == 2
    assert body["emails_queued"] == 0

    items = client.get("/api/v1/notifications", headers=learner_headers).json()["items"]
    assert items[0]["title"] == "Bảo trì hệ thống" and items[0]["type"] == "system"


def test_broadcast_by_role(client, db_session):
    _, admin_headers = _user(db_session, "bc.b1@example.com", role="admin")
    _, learner_headers = _user(db_session, "bc.b2@example.com")
    _, content_headers = _user(db_session, "bc.b3@example.com", role="content")

    r = client.post("/api/v1/admin/broadcast", headers=admin_headers, json={
        "title": "Chỉ cho biên tập viên", "audience": "role", "role": "content",
    })
    assert r.json()["recipients"] == 1

    assert client.get("/api/v1/notifications", headers=content_headers).json()["unread_count"] == 1
    assert client.get("/api/v1/notifications", headers=learner_headers).json()["unread_count"] == 0


def test_broadcast_role_without_role_rejected(client, db_session):
    _, headers = _user(db_session, "bc.c@example.com", role="admin")
    r = client.post("/api/v1/admin/broadcast", headers=headers,
                    json={"title": "Thiếu vai trò", "audience": "role"})
    assert r.status_code == 400


def test_broadcast_with_email_queues_messages(client, db_session):
    _, admin_headers = _user(db_session, "bc.d1@example.com", role="admin")
    _user(db_session, "bc.d2@example.com")
    _clear_verification_emails(db_session)

    r = client.post("/api/v1/admin/broadcast", headers=admin_headers, json={
        "title": "Sự kiện tháng 8", "body": "Chi tiết...", "send_email": True,
    })
    assert r.json()["emails_queued"] == 2

    rows = db_session.execute(select(EmailQueue)).scalars().all()
    assert len(rows) == 2 and all(e.template == "broadcast" for e in rows)


def test_broadcast_ignores_locked_users_and_writes_audit(client, db_session):
    admin, admin_headers = _user(db_session, "bc.e1@example.com", role="admin")
    locked, _ = _user(db_session, "bc.e2@example.com")
    client.patch(f"/api/v1/admin/users/{locked.id}/active",
                 json={"is_active": False}, headers=admin_headers)

    r = client.post("/api/v1/admin/broadcast", headers=admin_headers, json={"title": "Xin chào"})
    assert r.json()["recipients"] == 1   # chỉ còn admin

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "broadcast.send")
    ).scalars().one()
    assert entry.actor_id == admin.id and "1 người nhận" in entry.detail


def test_broadcast_type_system_ignores_preferences(client, db_session):
    """Thông báo hệ thống không nằm trong tùy chọn UC-60 nên vẫn tới nơi."""
    _, admin_headers = _user(db_session, "bc.f1@example.com", role="admin")
    learner, learner_headers = _user(db_session, "bc.f2@example.com")
    settings_row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == learner.id)
    ).scalar_one()
    settings_row.notify_review = False
    settings_row.notify_achievement = False
    settings_row.notify_community = False
    db_session.commit()

    client.post("/api/v1/admin/broadcast", headers=admin_headers, json={"title": "Thông báo chung"})
    assert client.get("/api/v1/notifications", headers=learner_headers).json()["unread_count"] == 1


# --- UC-80 -------------------------------------------------------------------

def test_email_queue_listing_and_counts(client, db_session):
    admin, headers = _user(db_session, "eq.a@example.com", role="admin")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, admin, to_email=admin.email, subject="Đã gửi", body="x")
    email_service.process_queue(db_session)
    email_service.enqueue(db_session, admin, to_email=admin.email, subject="Đang chờ", body="y")

    body = client.get("/api/v1/admin/emails", headers=headers).json()
    assert body["total"] == 2
    assert body["counts"] == {"sent": 1, "pending": 1}

    pending = client.get("/api/v1/admin/emails?status=pending", headers=headers).json()
    assert pending["total"] == 1 and pending["items"][0]["subject"] == "Đang chờ"


def test_retry_failed_email(client, db_session, monkeypatch):
    """UC-80 bước 2 — email 'failed' đưa lại về hàng đợi rồi gửi thành công."""
    admin, headers = _user(db_session, "eq.b@example.com", role="admin")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, admin, to_email=admin.email, subject="Lỗi", body="x")

    monkeypatch.setattr(email_service, "_send_now",
                        lambda _e: (_ for _ in ()).throw(RuntimeError("SMTP sập")))
    row = db_session.execute(select(EmailQueue)).scalars().one()
    for _ in range(email_service.MAX_ATTEMPTS):
        row.scheduled_at = None
        db_session.commit()
        email_service.process_queue(db_session)
    db_session.refresh(row)
    assert row.status == "failed"

    monkeypatch.undo()
    r = client.post(f"/api/v1/admin/emails/{row.id}/retry", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "pending" and r.json()["attempts"] == 0
    assert r.json()["last_error"] is None

    assert client.post("/api/v1/admin/jobs/send-emails", headers=headers).json()["sent"] == 1


def test_retry_sent_email_conflict(client, db_session):
    admin, headers = _user(db_session, "eq.c@example.com", role="admin")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, admin, to_email=admin.email, subject="OK", body="x")
    email_service.process_queue(db_session)
    row = db_session.execute(select(EmailQueue)).scalars().one()

    assert client.post(f"/api/v1/admin/emails/{row.id}/retry", headers=headers).status_code == 409


def test_delete_email(client, db_session):
    admin, headers = _user(db_session, "eq.d@example.com", role="admin")
    _clear_verification_emails(db_session)
    email_service.enqueue(db_session, admin, to_email=admin.email, subject="Xóa", body="x")
    row = db_session.execute(select(EmailQueue)).scalars().one()

    assert client.delete(f"/api/v1/admin/emails/{row.id}", headers=headers).status_code == 204
    assert client.get("/api/v1/admin/emails", headers=headers).json()["total"] == 0
    assert client.delete(f"/api/v1/admin/emails/{row.id}", headers=headers).status_code == 404


def test_email_and_broadcast_require_admin(client, db_session):
    _, learner = _user(db_session, "eq.e@example.com")
    assert client.get("/api/v1/admin/emails", headers=learner).status_code == 403
    assert client.post("/api/v1/admin/broadcast", headers=learner,
                       json={"title": "x"}).status_code == 403
