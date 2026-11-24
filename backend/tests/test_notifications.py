"""UC-58 xem · UC-59 quản lý · UC-60 tùy chọn · UC-61 sinh thông báo từ sự kiện."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.notification import Notification
from app.schemas.auth import RegisterRequest
from app.services import notification_service
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _post(client, headers, content="Bài viết"):
    return client.post("/api/v1/community/posts",
                       json={"post_type": "tip", "content": content}, headers=headers).json()


def test_list_and_unread_count(client, db_session):
    """UC-58 — danh sách + badge số chưa đọc."""
    user, headers = _user(db_session, "nt.a@example.com")
    notification_service.notify(db_session, user.id, type_="system", title="Chào mừng")
    notification_service.notify(db_session, user.id, type_="system", title="Bảo trì", link="/")

    body = client.get("/api/v1/notifications", headers=headers).json()
    assert body["unread_count"] == 2
    assert [n["title"] for n in body["items"]] == ["Bảo trì", "Chào mừng"]  # mới nhất trước


def test_mark_read_and_read_all(client, db_session):
    """UC-59 — đọc một / đọc tất cả."""
    user, headers = _user(db_session, "nt.b@example.com")
    first = notification_service.notify(db_session, user.id, type_="system", title="A")
    notification_service.notify(db_session, user.id, type_="system", title="B")

    r = client.post(f"/api/v1/notifications/{first.id}/read", headers=headers)
    assert r.status_code == 200 and r.json()["is_read"] is True
    assert client.get("/api/v1/notifications", headers=headers).json()["unread_count"] == 1

    assert client.post("/api/v1/notifications/read-all", headers=headers).json()["marked"] == 1
    assert client.get("/api/v1/notifications", headers=headers).json()["unread_count"] == 0


def test_delete_and_ownership(client, db_session):
    """UC-59 xóa; thông báo của người khác -> 404 (không lộ tồn tại)."""
    owner, owner_headers = _user(db_session, "nt.c1@example.com")
    _, other_headers = _user(db_session, "nt.c2@example.com")
    n = notification_service.notify(db_session, owner.id, type_="system", title="Riêng tư")

    assert client.post(f"/api/v1/notifications/{n.id}/read", headers=other_headers).status_code == 404
    assert client.delete(f"/api/v1/notifications/{n.id}", headers=other_headers).status_code == 404

    assert client.delete(f"/api/v1/notifications/{n.id}", headers=owner_headers).status_code == 204
    assert client.get("/api/v1/notifications", headers=owner_headers).json()["items"] == []


def test_unread_only_filter(client, db_session):
    user, headers = _user(db_session, "nt.d@example.com")
    read_one = notification_service.notify(db_session, user.id, type_="system", title="Đã đọc")
    notification_service.notify(db_session, user.id, type_="system", title="Chưa đọc")
    client.post(f"/api/v1/notifications/{read_one.id}/read", headers=headers)

    items = client.get("/api/v1/notifications?unread_only=true", headers=headers).json()["items"]
    assert [n["title"] for n in items] == ["Chưa đọc"]


def test_preferences_block_notification(client, db_session):
    """UC-60 + UC-61 E1 — tắt loại nào thì không sinh thông báo loại đó."""
    user, headers = _user(db_session, "nt.e@example.com")

    prefs = client.put("/api/v1/notifications/preferences", headers=headers, json={
        "notify_review": True, "notify_achievement": False, "notify_community": True,
    }).json()
    assert prefs["notify_achievement"] is False

    assert notification_service.notify(db_session, user.id, type_="achievement", title="X") is None
    assert notification_service.notify(db_session, user.id, type_="review_due", title="Y") is not None
    # loại 'system' không nằm trong tùy chọn -> luôn gửi
    assert notification_service.notify(db_session, user.id, type_="system", title="Z") is not None

    titles = {n["title"] for n in client.get("/api/v1/notifications", headers=headers).json()["items"]}
    assert titles == {"Y", "Z"}


def test_comment_notifies_post_author(client, db_session):
    """UC-50 bước 3 — bình luận bài người khác thì tác giả nhận thông báo."""
    author, author_headers = _user(db_session, "nt.f1@example.com")
    _, reader_headers = _user(db_session, "nt.f2@example.com")
    post = _post(client, author_headers)

    client.post(f"/api/v1/community/posts/{post['id']}/comments",
                json={"content": "Hay quá"}, headers=reader_headers)

    items = client.get("/api/v1/notifications", headers=author_headers).json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "community" and "bình luận" in items[0]["title"]
    assert items[0]["link"] == "/community"


def test_like_notifies_author_but_not_self(client, db_session):
    """UC-51 — thích bài người khác sinh thông báo; tự thích bài mình thì không."""
    author, author_headers = _user(db_session, "nt.g1@example.com")
    _, other_headers = _user(db_session, "nt.g2@example.com")
    post = _post(client, author_headers)

    client.post(f"/api/v1/community/posts/{post['id']}/like", headers=author_headers)
    assert client.get("/api/v1/notifications", headers=author_headers).json()["unread_count"] == 0

    client.post(f"/api/v1/community/posts/{post['id']}/like", headers=other_headers)
    items = client.get("/api/v1/notifications", headers=author_headers).json()["items"]
    assert len(items) == 1 and "thích" in items[0]["title"]

    # bỏ thích -> không sinh thêm thông báo
    client.post(f"/api/v1/community/posts/{post['id']}/like", headers=other_headers)
    rows = db_session.execute(
        select(Notification).where(Notification.user_id == author.id)
    ).scalars().all()
    assert len(rows) == 1


def test_notifications_require_auth(client):
    assert client.get("/api/v1/notifications").status_code == 401
