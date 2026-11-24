"""UC-77 kiểm duyệt bài viết · UC-78 xử lý báo cáo (Admin)."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.item import Item
from app.models.post import Post
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service
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


def _post(client, headers, content="Bài viết"):
    return client.post("/api/v1/community/posts",
                       json={"post_type": "tip", "content": content}, headers=headers).json()


def _public_set(db_session, owner_id, name):
    ws = WordSet(owner_id=owner_id, name=name, is_public=True, is_featured=True,
                 category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    db_session.add(Item(word_set_id=ws.id, word="w", meaning="m"))
    db_session.commit()
    db_session.refresh(ws)
    return ws


# --- UC-77 -------------------------------------------------------------------

def test_approve_pending_post_publishes_it(client, db_session):
    """Khép vòng UC-49 Q3: bật duyệt -> bài chờ -> Admin duyệt -> lên feed."""
    config_service.set_values(db_session, {"require_post_approval": True})
    _, admin_headers = _user(db_session, "md.a1@example.com", role="admin")
    author, author_headers = _user(db_session, "md.a2@example.com")

    post = _post(client, author_headers, "Bài chờ duyệt")
    assert post["status"] == "pending"
    assert client.get("/api/v1/community/posts", headers=author_headers).json()["total"] == 0

    queue = client.get("/api/v1/admin/posts", headers=admin_headers).json()
    assert queue["total"] == 1 and queue["items"][0]["author_name"] == "md.a"

    r = client.patch(f"/api/v1/admin/posts/{post['id']}",
                     json={"decision": "approve"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "approved"

    assert client.get("/api/v1/community/posts", headers=author_headers).json()["total"] == 1
    # tác giả được báo (UC-61)
    titles = [n["title"] for n in
              client.get("/api/v1/notifications", headers=author_headers).json()["items"]]
    assert "Bài viết của bạn đã được duyệt" in titles


def test_reject_post_keeps_it_off_feed(client, db_session):
    config_service.set_values(db_session, {"require_post_approval": True})
    _, admin_headers = _user(db_session, "md.b1@example.com", role="admin")
    _, author_headers = _user(db_session, "md.b2@example.com")
    post = _post(client, author_headers)

    r = client.patch(f"/api/v1/admin/posts/{post['id']}",
                     json={"decision": "reject", "reason": "Sai nội dung"}, headers=admin_headers)
    assert r.json()["status"] == "rejected"
    assert client.get("/api/v1/community/posts", headers=author_headers).json()["total"] == 0
    assert client.get("/api/v1/admin/posts", headers=admin_headers).json()["total"] == 0


def test_remove_published_post(client, db_session):
    """Gỡ bài đã hiển thị = xóa mềm (Q6), bản ghi vẫn còn."""
    _, admin_headers = _user(db_session, "md.c1@example.com", role="admin")
    _, author_headers = _user(db_session, "md.c2@example.com")
    post = _post(client, author_headers, "Bài vi phạm")

    r = client.patch(f"/api/v1/admin/posts/{post['id']}",
                     json={"decision": "remove", "reason": "Spam"}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/v1/community/posts", headers=author_headers).json()["total"] == 0

    row = db_session.execute(select(Post).where(Post.id == post["id"])).scalars().one()
    assert row.deleted_at is not None

    entry = db_session.execute(
        select(AuditLog).where(AuditLog.action == "post.remove")
    ).scalars().one()
    assert entry.detail == "Spam"


def test_moderation_requires_admin(client, db_session):
    _, learner = _user(db_session, "md.d@example.com")
    assert client.get("/api/v1/admin/posts", headers=learner).status_code == 403
    assert client.get("/api/v1/admin/reports", headers=learner).status_code == 403


# --- UC-78 -------------------------------------------------------------------

def test_report_queue_shows_target_preview(client, db_session):
    _, admin_headers = _user(db_session, "md.e1@example.com", role="admin")
    owner, _ = _user(db_session, "md.e2@example.com")
    _, reporter_headers = _user(db_session, "md.e3@example.com")
    ws = _public_set(db_session, owner.id, "Bộ bị báo")
    client.post(f"/api/v1/discover/{ws.id}/report",
                json={"reason": "spam", "description": "Toàn quảng cáo"}, headers=reporter_headers)

    body = client.get("/api/v1/admin/reports", headers=admin_headers).json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["target_type"] == "word_set" and row["target_preview"] == "Bộ bị báo"
    assert row["target_exists"] is True and row["reporter_name"] == "md.e"


def test_dismiss_report(client, db_session):
    _, admin_headers = _user(db_session, "md.f1@example.com", role="admin")
    owner, _ = _user(db_session, "md.f2@example.com")
    _, reporter_headers = _user(db_session, "md.f3@example.com")
    ws = _public_set(db_session, owner.id, "Bộ ổn")
    report = client.post(f"/api/v1/discover/{ws.id}/report",
                         json={"reason": "spam"}, headers=reporter_headers).json()

    r = client.patch(f"/api/v1/admin/reports/{report['id']}",
                     json={"decision": "dismiss", "note": "Không vi phạm"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    assert r.json()["resolved_at"] is not None

    db_session.refresh(ws)
    assert ws.is_public is True                       # nội dung giữ nguyên
    assert client.get("/api/v1/admin/reports", headers=admin_headers).json()["total"] == 0


def test_resolve_report_removes_word_set_from_public(client, db_session):
    """Gỡ bộ từ bị báo cáo: hết công khai + hết nổi bật, chủ sở hữu được báo."""
    _, admin_headers = _user(db_session, "md.g1@example.com", role="admin")
    owner, owner_headers = _user(db_session, "md.g2@example.com")
    _, reporter_headers = _user(db_session, "md.g3@example.com")
    ws = _public_set(db_session, owner.id, "Bộ vi phạm")
    report = client.post(f"/api/v1/discover/{ws.id}/report",
                         json={"reason": "copyright"}, headers=reporter_headers).json()

    r = client.patch(f"/api/v1/admin/reports/{report['id']}",
                     json={"decision": "remove_content", "note": "Vi phạm bản quyền"},
                     headers=admin_headers)
    assert r.json()["status"] == "resolved" and r.json()["target_exists"] is False

    db_session.refresh(ws)
    assert ws.is_public is False and ws.is_featured is False
    assert client.get(f"/api/v1/discover/{ws.id}", headers=reporter_headers).status_code == 404

    titles = [n["title"] for n in
              client.get("/api/v1/notifications", headers=owner_headers).json()["items"]]
    assert any("đã bị gỡ khỏi kho công khai" in t for t in titles)


def test_resolve_report_removes_post(client, db_session):
    _, admin_headers = _user(db_session, "md.h1@example.com", role="admin")
    author, author_headers = _user(db_session, "md.h2@example.com")
    _, reporter_headers = _user(db_session, "md.h3@example.com")
    post = _post(client, author_headers, "Nội dung xấu")
    report = client.post(f"/api/v1/community/posts/{post['id']}/report",
                         json={"reason": "offensive"}, headers=reporter_headers).json()

    client.patch(f"/api/v1/admin/reports/{report['id']}",
                 json={"decision": "remove_content"}, headers=admin_headers)

    assert client.get("/api/v1/community/posts", headers=author_headers).json()["total"] == 0
    titles = [n["title"] for n in
              client.get("/api/v1/notifications", headers=author_headers).json()["items"]]
    assert any("bị gỡ do vi phạm" in t for t in titles)


def test_report_cannot_be_resolved_twice(client, db_session):
    _, admin_headers = _user(db_session, "md.i1@example.com", role="admin")
    owner, _ = _user(db_session, "md.i2@example.com")
    _, reporter_headers = _user(db_session, "md.i3@example.com")
    ws = _public_set(db_session, owner.id, "Bộ đôi")
    report = client.post(f"/api/v1/discover/{ws.id}/report",
                         json={"reason": "spam"}, headers=reporter_headers).json()

    assert client.patch(f"/api/v1/admin/reports/{report['id']}",
                        json={"decision": "dismiss"}, headers=admin_headers).status_code == 200
    assert client.patch(f"/api/v1/admin/reports/{report['id']}",
                        json={"decision": "dismiss"}, headers=admin_headers).status_code == 409
