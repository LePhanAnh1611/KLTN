"""UC-12 xóa tài khoản · UC-32 đánh dấu từ khó."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.auth_token import AuthToken
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.post import Post
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user

PASSWORD = "Abcd1234"


def _setup(db_session, email: str, n_items: int = 2):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password=PASSWORD, password_confirm=PASSWORD,
                        display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set0", category="Gen", difficulty="beginner",
                 is_public=True)
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"w{i}", meaning=f"m{i}") for i in range(n_items)]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


# ---------------------------------------------------------------- UC-32

def test_flag_and_list_item(client, db_session):
    user, headers, ws, items = _setup(db_session, "fl.a@example.com")
    db_session.add(KnowledgeState(user_id=user.id, item_id=items[0].id, mastery=0.92,
                                  last_updated=datetime.now(timezone.utc)))
    db_session.commit()

    r = client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=headers,
                   json={"note": "hay nhầm với w1"})
    assert r.status_code == 200

    rows = client.get("/api/v1/me/flagged-items", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["word"] == "w0"
    assert rows[0]["note"] == "hay nhầm với w1"
    assert rows[0]["word_set_name"] == "Set0"
    # mastery cao vẫn đánh dấu được — cảm nhận chủ quan khác số liệu DKT
    assert rows[0]["mastery"] == 0.92


def test_flag_is_idempotent_and_updates_note(client, db_session):
    _, headers, _, items = _setup(db_session, "fl.b@example.com")
    client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=headers, json={"note": "a"})
    client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=headers, json={"note": "b"})

    rows = client.get("/api/v1/me/flagged-items", headers=headers).json()
    assert len(rows) == 1 and rows[0]["note"] == "b"


def test_flag_without_mastery_returns_null(client, db_session):
    """Từ chưa từng học thì chưa có mastery để đối chiếu."""
    _, headers, _, items = _setup(db_session, "fl.c@example.com")
    client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=headers, json={})

    assert client.get("/api/v1/me/flagged-items", headers=headers).json()[0]["mastery"] is None


def test_clear_flag_is_forgiving(client, db_session):
    _, headers, _, items = _setup(db_session, "fl.d@example.com")
    client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=headers, json={})

    assert client.delete(f"/api/v1/me/flagged-items/{items[0].id}",
                         headers=headers).status_code == 204
    assert client.get("/api/v1/me/flagged-items", headers=headers).json() == []
    # bỏ đánh dấu lần nữa: không có gì để làm, cũng không phải lỗi
    assert client.delete(f"/api/v1/me/flagged-items/{items[0].id}",
                         headers=headers).status_code == 204


def test_cannot_flag_item_outside_own_library(client, db_session):
    _, _, _, items = _setup(db_session, "fl.e@example.com")
    _, other, _, _ = _setup(db_session, "fl.f@example.com")

    assert client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=other,
                      json={}).status_code == 404


def test_flags_are_per_user(client, db_session):
    _, headers, _, items = _setup(db_session, "fl.g@example.com")
    _, other, _, _ = _setup(db_session, "fl.h@example.com")
    client.put(f"/api/v1/me/flagged-items/{items[0].id}", headers=headers, json={})

    assert client.get("/api/v1/me/flagged-items", headers=other).json() == []


# ---------------------------------------------------------------- UC-12

def test_delete_account_soft_deletes_and_frees_email(client, db_session):
    user, headers, ws, _ = _setup(db_session, "del.a@example.com")
    user_id = user.id

    r = client.request("DELETE", "/api/v1/users/me", headers=headers,
                       json={"password": PASSWORD, "confirm": True})
    assert r.status_code == 204, r.text

    db_session.expire_all()
    row = db_session.get(User, user_id)
    assert row is not None                    # xóa MỀM, hàng vẫn còn (Q6)
    assert row.deleted_at is not None
    assert row.is_active is False
    assert row.email != "del.a@example.com"   # đã ẩn danh
    assert row.display_name == "Người dùng đã xóa"

    # bộ từ riêng bị gỡ khỏi Khám phá
    db_session.refresh(ws)
    assert ws.deleted_at is not None and ws.is_public is False

    # địa chỉ email cũ dùng đăng ký lại được
    again = client.post("/api/v1/auth/register", json={
        "email": "del.a@example.com", "password": PASSWORD,
        "password_confirm": PASSWORD, "display_name": "Mới",
    })
    assert again.status_code == 201, again.text


def test_deleted_account_cannot_login_or_use_token(client, db_session):
    _, headers, _, _ = _setup(db_session, "del.b@example.com")
    client.request("DELETE", "/api/v1/users/me", headers=headers,
                   json={"password": PASSWORD, "confirm": True})

    # token cũ chết ngay (get_current_user chặn theo is_active)
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "del.b@example.com", "password": PASSWORD,
    }).status_code == 401


def test_delete_account_removes_posts_and_tokens(client, db_session):
    user, headers, _, _ = _setup(db_session, "del.c@example.com")
    client.post("/api/v1/community/posts", headers=headers,
                json={"post_type": "tip", "content": "mẹo học"})

    client.request("DELETE", "/api/v1/users/me", headers=headers,
                   json={"password": PASSWORD, "confirm": True})

    db_session.expire_all()
    posts = db_session.execute(
        select(Post).where(Post.author_id == user.id)
    ).scalars().all()
    assert posts and all(p.deleted_at is not None for p in posts)

    tokens = db_session.execute(
        select(AuthToken).where(AuthToken.user_id == user.id)
    ).scalars().all()
    assert tokens == []


def test_delete_account_keeps_interactions(client, db_session, monkeypatch):
    """Interaction là dữ liệu huấn luyện DKT — xóa tài khoản không được xóa nó."""
    from app.models.interaction import Interaction
    from app.services import dkt_client

    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    user, headers, ws, items = _setup(db_session, "del.d@example.com")
    sid = client.post("/api/v1/sessions", headers=headers,
                      json={"word_set_id": ws.id, "mode": "flashcard"}).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                json={"item_id": items[0].id, "is_correct": True})
    client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)

    client.request("DELETE", "/api/v1/users/me", headers=headers,
                   json={"password": PASSWORD, "confirm": True})

    db_session.expire_all()
    kept = db_session.execute(
        select(Interaction).where(Interaction.user_id == user.id)
    ).scalars().all()
    assert len(kept) == 1


def test_delete_account_rejects_wrong_password(client, db_session):
    _, headers, _, _ = _setup(db_session, "del.e@example.com")
    r = client.request("DELETE", "/api/v1/users/me", headers=headers,
                       json={"password": "SaiRoi123", "confirm": True})
    assert r.status_code == 400
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200


def test_delete_account_requires_confirmation(client, db_session):
    _, headers, _, _ = _setup(db_session, "del.f@example.com")
    r = client.request("DELETE", "/api/v1/users/me", headers=headers,
                       json={"password": PASSWORD, "confirm": False})
    assert r.status_code == 400
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200


def test_new_endpoints_require_auth(client):
    assert client.get("/api/v1/me/flagged-items").status_code == 401
    assert client.request("DELETE", "/api/v1/users/me",
                          json={"password": "x", "confirm": True}).status_code == 401
