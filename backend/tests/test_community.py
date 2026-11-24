"""UC-49 đăng bài · UC-50 bình luận · UC-51 thích · UC-52 xóa · UC-53 báo cáo bài."""
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.post import Post
from app.models.report import Report
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _post(client, headers, content="Mẹo học từ vựng", post_type="tip", image_url=None):
    body = {"post_type": post_type, "content": content}
    if image_url:
        body["image_url"] = image_url
    r = client.post("/api/v1/community/posts", json=body, headers=headers)
    assert r.status_code == 201
    return r.json()


def test_create_and_list_feed(client, db_session):
    """UC-49: bài hiện ngay ở feed (require_post_approval=False -> 'approved')."""
    _, headers = _user(db_session, "cm.a@example.com")
    created = _post(client, headers, "Học 10 từ mỗi ngày", image_url="https://x.test/a.png")

    assert created["status"] == "approved"
    assert created["is_mine"] is True and created["like_count"] == 0

    feed = client.get("/api/v1/community/posts", headers=headers).json()
    assert feed["total"] == 1
    card = feed["items"][0]
    assert card["content"] == "Học 10 từ mỗi ngày"
    assert card["image_url"] == "https://x.test/a.png"
    assert card["author_name"] == "cm.a"


def test_create_post_empty_content_rejected(client, db_session):
    """UC-49 E1: nội dung rỗng -> chặn."""
    _, headers = _user(db_session, "cm.b@example.com")
    assert client.post("/api/v1/community/posts",
                       json={"post_type": "tip", "content": ""}, headers=headers).status_code == 422
    assert client.post("/api/v1/community/posts",
                       json={"post_type": "tip", "content": "   "}, headers=headers).status_code == 400


def test_feed_filter_by_type(client, db_session):
    _, headers = _user(db_session, "cm.c@example.com")
    _post(client, headers, "Mẹo hay", post_type="tip")
    _post(client, headers, "Từ nào đây?", post_type="question")

    feed = client.get("/api/v1/community/posts?post_type=question", headers=headers).json()
    assert feed["total"] == 1 and feed["items"][0]["content"] == "Từ nào đây?"


def test_comment_flow(client, db_session):
    """UC-50: bình luận hiện dưới bài; rỗng -> chặn."""
    _, author = _user(db_session, "cm.d1@example.com")
    _, reader = _user(db_session, "cm.d2@example.com")
    post = _post(client, author)

    r = client.post(f"/api/v1/community/posts/{post['id']}/comments",
                    json={"content": "Cảm ơn bạn!"}, headers=reader)
    assert r.status_code == 201 and r.json()["is_mine"] is True

    assert client.post(f"/api/v1/community/posts/{post['id']}/comments",
                       json={"content": "  "}, headers=reader).status_code == 400

    comments = client.get(f"/api/v1/community/posts/{post['id']}/comments", headers=author).json()
    assert len(comments) == 1
    assert comments[0]["author_name"] == "cm.d" and comments[0]["is_mine"] is False

    feed = client.get("/api/v1/community/posts", headers=author).json()
    assert feed["items"][0]["comment_count"] == 1


def test_like_toggle(client, db_session):
    """UC-51: bấm 2 lần = thích rồi bỏ thích (một react/người/bài)."""
    _, author = _user(db_session, "cm.e1@example.com")
    _, other = _user(db_session, "cm.e2@example.com")
    post = _post(client, author)

    first = client.post(f"/api/v1/community/posts/{post['id']}/like", headers=other).json()
    assert first["liked_by_me"] is True and first["like_count"] == 1

    second = client.post(f"/api/v1/community/posts/{post['id']}/like", headers=other).json()
    assert second["liked_by_me"] is False and second["like_count"] == 0

    client.post(f"/api/v1/community/posts/{post['id']}/like", headers=other)
    feed = client.get("/api/v1/community/posts", headers=author).json()
    assert feed["items"][0]["like_count"] == 1
    assert feed["items"][0]["liked_by_me"] is False  # tác giả chưa thích bài mình


def test_delete_own_post_only(client, db_session):
    """UC-52: E1 không phải tác giả -> 403; xóa mềm bài + ẩn bình luận."""
    _, author = _user(db_session, "cm.f1@example.com")
    _, other = _user(db_session, "cm.f2@example.com")
    post = _post(client, author)
    client.post(f"/api/v1/community/posts/{post['id']}/comments",
                json={"content": "hay quá"}, headers=other)

    assert client.delete(f"/api/v1/community/posts/{post['id']}", headers=other).status_code == 403
    assert client.delete(f"/api/v1/community/posts/{post['id']}", headers=author).status_code == 204

    assert client.get("/api/v1/community/posts", headers=author).json()["total"] == 0
    assert client.get(f"/api/v1/community/posts/{post['id']}/comments", headers=author).status_code == 404

    # Q6: xóa mềm — bản ghi vẫn còn trong DB
    assert db_session.execute(
        select(func.count()).select_from(Post).where(Post.id == post["id"])
    ).scalar_one() == 1


def test_report_post(client, db_session):
    """UC-53: tạo REPORT target_type='post'; báo cáo trùng -> gộp."""
    _, author = _user(db_session, "cm.g1@example.com")
    _, other = _user(db_session, "cm.g2@example.com")
    post = _post(client, author, "Nội dung xấu")

    r = client.post(f"/api/v1/community/posts/{post['id']}/report",
                    json={"reason": "offensive"}, headers=other)
    assert r.status_code == 201
    assert r.json()["target_type"] == "post" and r.json()["merged"] is False

    again = client.post(f"/api/v1/community/posts/{post['id']}/report",
                        json={"reason": "spam"}, headers=other).json()
    assert again["merged"] is True

    assert db_session.execute(
        select(func.count()).select_from(Report)
        .where(Report.target_type == "post", Report.target_id == post["id"])
    ).scalar_one() == 1


def test_actions_on_deleted_post_404(client, db_session):
    _, author = _user(db_session, "cm.h@example.com")
    post = _post(client, author)
    client.delete(f"/api/v1/community/posts/{post['id']}", headers=author)

    pid = post["id"]
    assert client.post(f"/api/v1/community/posts/{pid}/like", headers=author).status_code == 404
    assert client.post(f"/api/v1/community/posts/{pid}/comments",
                       json={"content": "x"}, headers=author).status_code == 404
    assert client.post(f"/api/v1/community/posts/{pid}/report",
                       json={"reason": "spam"}, headers=author).status_code == 404


def test_pending_post_hidden_from_feed(client, db_session):
    """Q3: bật kiểm duyệt (UC-81) thì bài phải chờ duyệt, không lên feed."""
    from app.services import config_service

    config_service.set_values(db_session, {"require_post_approval": True})
    _, headers = _user(db_session, "cm.i@example.com")

    created = _post(client, headers, "Bài chờ duyệt")
    assert created["status"] == "pending"
    assert client.get("/api/v1/community/posts", headers=headers).json()["total"] == 0


def test_community_requires_auth(client):
    assert client.get("/api/v1/community/posts").status_code == 401
