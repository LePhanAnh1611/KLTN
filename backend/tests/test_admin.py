"""UC-72 tổng quan · UC-73 quản lý người dùng · UC-83 nhật ký hệ thống."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.item import Item
from app.models.session import StudySession
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
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


# --- UC-72 -------------------------------------------------------------------

def test_overview_counts(client, db_session):
    admin, headers = _user(db_session, "ad.a1@example.com", role="admin")
    learner, _ = _user(db_session, "ad.a2@example.com")

    ws = WordSet(owner_id=learner.id, name="Bộ công khai", is_public=True)
    db_session.add(ws)
    db_session.flush()
    db_session.add(Item(word_set_id=ws.id, word="a", meaning="b"))
    now = datetime.now(timezone.utc)
    db_session.add(StudySession(
        user_id=learner.id, status="completed", started_at=now, ended_at=now,
        item_count=5, correct_count=4, xp_earned=40,
    ))
    db_session.commit()

    body = client.get("/api/v1/admin/overview", headers=headers).json()
    assert body["total_users"] >= 2 and body["active_users"] >= 2
    assert body["dau"] == 1 and body["mau"] == 1
    assert body["total_word_sets"] == 1 and body["public_word_sets"] == 1
    assert body["total_items"] == 1 and body["total_sessions"] == 1
    assert body["pending_reports"] == 0


def test_admin_endpoints_require_admin_role(client, db_session):
    _, learner = _user(db_session, "ad.b@example.com")
    for path in ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/audit-logs"):
        assert client.get(path, headers=learner).status_code == 403
        assert client.get(path).status_code == 401


# --- UC-73 -------------------------------------------------------------------

def test_list_and_search_users(client, db_session):
    _, headers = _user(db_session, "ad.c1@example.com", role="admin")
    _user(db_session, "nguyenvan.a@example.com")

    body = client.get("/api/v1/admin/users?q=nguyenvan", headers=headers).json()
    assert body["total"] == 1 and body["items"][0]["email"] == "nguyenvan.a@example.com"

    admins = client.get("/api/v1/admin/users?role=admin", headers=headers).json()
    assert all(u["role"] == "admin" for u in admins["items"])
    assert any(u["is_me"] for u in admins["items"])


def test_lock_and_unlock_user_writes_audit(client, db_session):
    admin, headers = _user(db_session, "ad.d1@example.com", role="admin")
    target, target_headers = _user(db_session, "ad.d2@example.com")

    r = client.patch(f"/api/v1/admin/users/{target.id}/active",
                     json={"is_active": False, "reason": "Spam"}, headers=headers)
    assert r.status_code == 200 and r.json()["is_active"] is False

    # UC-73 hậu điều kiện: tài khoản bị khóa không dùng được token nữa
    assert client.get("/api/v1/users/me", headers=target_headers).status_code == 401

    client.patch(f"/api/v1/admin/users/{target.id}/active",
                 json={"is_active": True}, headers=headers)
    assert client.get("/api/v1/users/me", headers=target_headers).status_code == 200

    actions = db_session.execute(
        select(AuditLog.action).where(AuditLog.target_id == target.id).order_by(AuditLog.id)
    ).scalars().all()
    assert actions == ["user.lock", "user.unlock"]


def test_change_role_writes_audit(client, db_session):
    _, headers = _user(db_session, "ad.e1@example.com", role="admin")
    target, _ = _user(db_session, "ad.e2@example.com")

    r = client.patch(f"/api/v1/admin/users/{target.id}/role",
                     json={"role": "content"}, headers=headers)
    assert r.status_code == 200 and r.json()["role"] == "content"

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.target_id == target.id)
    ).scalars().one()
    assert entry.action == "user.role_change" and entry.detail == "learner -> content"


def test_cannot_lock_or_demote_self(client, db_session):
    """UC-73 E1 — tự khóa / tự hạ quyền chính mình bị chặn."""
    admin, headers = _user(db_session, "ad.f@example.com", role="admin")

    assert client.patch(f"/api/v1/admin/users/{admin.id}/active",
                        json={"is_active": False}, headers=headers).status_code == 400
    assert client.patch(f"/api/v1/admin/users/{admin.id}/role",
                        json={"role": "learner"}, headers=headers).status_code == 400


def test_invalid_role_rejected(client, db_session):
    _, headers = _user(db_session, "ad.g1@example.com", role="admin")
    target, _ = _user(db_session, "ad.g2@example.com")
    assert client.patch(f"/api/v1/admin/users/{target.id}/role",
                        json={"role": "superuser"}, headers=headers).status_code == 422


# --- UC-83 -------------------------------------------------------------------

def test_audit_log_listing_and_filter(client, db_session):
    admin, headers = _user(db_session, "ad.h1@example.com", role="admin")
    target, _ = _user(db_session, "ad.h2@example.com")
    client.patch(f"/api/v1/admin/users/{target.id}/role", json={"role": "content"}, headers=headers)
    client.patch(f"/api/v1/admin/users/{target.id}/active", json={"is_active": False}, headers=headers)

    body = client.get("/api/v1/admin/audit-logs", headers=headers).json()
    assert body["total"] == 2
    assert body["items"][0]["action"] == "user.lock"          # mới nhất trước
    assert body["items"][0]["actor_name"] == admin.display_name

    filtered = client.get("/api/v1/admin/audit-logs?action=user.role_change", headers=headers).json()
    assert filtered["total"] == 1 and filtered["items"][0]["detail"] == "learner -> content"
