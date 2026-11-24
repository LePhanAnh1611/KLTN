"""UC-74 — vai trò & phân quyền (ma trận có hiệu lực thật lên endpoint)."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.schemas.auth import RegisterRequest
from app.services import permission_service
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


def test_matrix_defaults(client, db_session):
    _, headers = _user(db_session, "pm.a@example.com", role="admin")

    body = client.get("/api/v1/admin/permissions", headers=headers).json()
    assert body["roles"] == list(permission_service.ROLES)
    assert len(body["permissions"]) == len(permission_service.PERMISSIONS)
    assert set(body["matrix"]["admin"]) == {p.key for p in permission_service.PERMISSIONS}
    assert body["matrix"]["learner"] == []
    assert "admin.users" not in body["matrix"]["content"]     # biên tập viên không quản người dùng
    assert "admin.moderation" in body["matrix"]["content"]


def test_content_role_default_access(client, db_session):
    """Vai trò 'content' vào được kiểm duyệt/bộ từ nhưng không vào được người dùng/cấu hình."""
    _, headers = _user(db_session, "pm.b@example.com", role="content")

    assert client.get("/api/v1/admin/posts", headers=headers).status_code == 200
    assert client.get("/api/v1/admin/word-sets", headers=headers).status_code == 200
    assert client.get("/api/v1/admin/reports", headers=headers).status_code == 200

    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/config", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/permissions", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=headers).status_code == 403


def test_granting_permission_opens_endpoint(client, db_session):
    """Gán quyền cho vai trò -> endpoint mở ra ngay, không cần sửa code."""
    _, admin_headers = _user(db_session, "pm.c1@example.com", role="admin")
    _, content_headers = _user(db_session, "pm.c2@example.com", role="content")

    assert client.get("/api/v1/admin/config", headers=content_headers).status_code == 403

    current = client.get("/api/v1/admin/permissions", headers=admin_headers).json()["matrix"]["content"]
    r = client.put("/api/v1/admin/permissions/content", headers=admin_headers,
                   json={"permissions": current + ["admin.config"]})
    assert r.status_code == 200

    assert client.get("/api/v1/admin/config", headers=content_headers).status_code == 200


def test_revoking_permission_closes_endpoint(client, db_session):
    _, admin_headers = _user(db_session, "pm.d1@example.com", role="admin")
    _, content_headers = _user(db_session, "pm.d2@example.com", role="content")

    assert client.get("/api/v1/admin/word-sets", headers=content_headers).status_code == 200

    client.put("/api/v1/admin/permissions/content", headers=admin_headers,
               json={"permissions": ["admin.overview"]})

    assert client.get("/api/v1/admin/word-sets", headers=content_headers).status_code == 403
    assert client.get("/api/v1/admin/overview", headers=content_headers).status_code == 200


def test_admin_cannot_drop_own_role_management(client, db_session):
    """Chặn tự khóa: vai trò admin luôn phải giữ quyền quản lý phân quyền."""
    _, headers = _user(db_session, "pm.e@example.com", role="admin")

    r = client.put("/api/v1/admin/permissions/admin", headers=headers,
                   json={"permissions": ["admin.overview"]})
    assert r.status_code == 400
    assert client.get("/api/v1/admin/permissions", headers=headers).status_code == 200


def test_invalid_role_or_permission_rejected(client, db_session):
    _, headers = _user(db_session, "pm.f@example.com", role="admin")

    assert client.put("/api/v1/admin/permissions/superuser", headers=headers,
                      json={"permissions": []}).status_code == 400
    assert client.put("/api/v1/admin/permissions/content", headers=headers,
                      json={"permissions": ["admin.khong_ton_tai"]}).status_code == 400


def test_permission_change_writes_audit(client, db_session):
    _, headers = _user(db_session, "pm.g@example.com", role="admin")
    client.put("/api/v1/admin/permissions/learner", headers=headers,
               json={"permissions": ["admin.overview"]})

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "role.permissions_change")
    ).scalars().one()
    assert entry.detail == "learner: +admin.overview"


def test_learner_has_no_admin_access(client, db_session):
    _, headers = _user(db_session, "pm.h@example.com")
    for path in ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/permissions",
                 "/api/v1/admin/categories", "/api/v1/admin/emails"):
        assert client.get(path, headers=headers).status_code == 403
    assert client.post("/api/v1/admin/jobs/run-reminders", headers=headers).status_code == 403
