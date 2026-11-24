"""UC-19/20/21 — khám phá, chi tiết/preview, tải (snapshot) bộ từ công khai."""
from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _public_set(db_session, owner_id, name, category="Gen", difficulty="beginner",
                n_items=5, is_public=True, downloads=0):
    ws = WordSet(owner_id=owner_id, name=name, category=category, difficulty=difficulty,
                 is_public=is_public, download_count=downloads)
    db_session.add(ws)
    db_session.flush()
    db_session.add_all([Item(word_set_id=ws.id, word=f"{name}_w{i}", meaning=f"m{i}") for i in range(n_items)])
    db_session.commit()
    db_session.refresh(ws)
    return ws


def test_list_public_basic(client, db_session):
    owner, _ = _user(db_session, "own.a@example.com")
    _public_set(db_session, owner.id, "Animals")
    _public_set(db_session, owner.id, "Food")
    _public_set(db_session, owner.id, "Secret", is_public=False)  # không xuất hiện

    _, headers = _user(db_session, "lrn.a@example.com")
    r = client.get("/api/v1/discover", headers=headers).json()
    names = {c["name"] for c in r["items"]}
    assert names == {"Animals", "Food"}
    assert r["total"] == 2
    assert all(c["item_count"] == 5 and c["is_downloaded"] is False for c in r["items"])


def test_list_search_and_filter(client, db_session):
    owner, _ = _user(db_session, "own.b@example.com")
    _public_set(db_session, owner.id, "Animals", category="Nature", difficulty="beginner")
    _public_set(db_session, owner.id, "Food", category="Daily", difficulty="advanced")
    _, headers = _user(db_session, "lrn.b@example.com")

    assert {c["name"] for c in client.get("/api/v1/discover?q=ani", headers=headers).json()["items"]} == {"Animals"}
    assert {c["name"] for c in client.get("/api/v1/discover?category=Daily", headers=headers).json()["items"]} == {"Food"}
    assert {c["name"] for c in client.get("/api/v1/discover?difficulty=advanced", headers=headers).json()["items"]} == {"Food"}


def test_list_sort_popular(client, db_session):
    owner, _ = _user(db_session, "own.c@example.com")
    _public_set(db_session, owner.id, "Low", downloads=1)
    _public_set(db_session, owner.id, "High", downloads=99)
    _, headers = _user(db_session, "lrn.c@example.com")
    items = client.get("/api/v1/discover?sort=popular", headers=headers).json()["items"]
    assert items[0]["name"] == "High"


def test_detail_preview(client, db_session):
    owner, _ = _user(db_session, "own.d@example.com")
    ws = _public_set(db_session, owner.id, "Colors", n_items=12)
    _, headers = _user(db_session, "lrn.d@example.com")
    d = client.get(f"/api/v1/discover/{ws.id}", headers=headers).json()
    assert d["item_count"] == 12
    assert len(d["preview_items"]) == 8  # PREVIEW_LIMIT
    assert d["owner_name"] == "own."
    assert d["is_downloaded"] is False


def test_download_snapshot(client, db_session):
    owner, _ = _user(db_session, "own.e@example.com")
    ws = _public_set(db_session, owner.id, "Verbs", n_items=4, downloads=0)
    learner, headers = _user(db_session, "lrn.e@example.com")

    r = client.post(f"/api/v1/discover/{ws.id}/download", headers=headers)
    assert r.status_code == 201
    clone = r.json()
    assert clone["item_count"] == 4
    assert clone["is_public"] is False

    # bản sao thuộc learner, gắn origin_set_id, tách khỏi bộ gốc
    clone_ws = db_session.get(WordSet, clone["id"])
    assert clone_ws.owner_id == learner.id
    assert clone_ws.origin_set_id == ws.id
    # download_count bộ gốc +1
    db_session.refresh(ws)
    assert ws.download_count == 1
    # xuất hiện trong thư viện (UC-16)
    lib = client.get("/api/v1/word-sets", headers=headers).json()
    assert any(w["id"] == clone["id"] for w in lib)
    # detail giờ báo đã tải
    assert client.get(f"/api/v1/discover/{ws.id}", headers=headers).json()["is_downloaded"] is True


def test_download_dedupe_conflict(client, db_session):
    owner, _ = _user(db_session, "own.f@example.com")
    ws = _public_set(db_session, owner.id, "Once")
    _, headers = _user(db_session, "lrn.f@example.com")
    assert client.post(f"/api/v1/discover/{ws.id}/download", headers=headers).status_code == 201
    assert client.post(f"/api/v1/discover/{ws.id}/download", headers=headers).status_code == 409


def test_download_nonpublic_404(client, db_session):
    owner, _ = _user(db_session, "own.g@example.com")
    ws = _public_set(db_session, owner.id, "Private", is_public=False)
    _, headers = _user(db_session, "lrn.g@example.com")
    assert client.post(f"/api/v1/discover/{ws.id}/download", headers=headers).status_code == 404
    assert client.get(f"/api/v1/discover/{ws.id}", headers=headers).status_code == 404


def test_discover_requires_auth(client):
    assert client.get("/api/v1/discover").status_code == 401


def test_featured_empty(client, db_session):
    """UC-22 E1: chưa có bộ nổi bật -> danh sách rỗng (frontend ẩn khu vực)."""
    owner, _ = _user(db_session, "own.h@example.com")
    _public_set(db_session, owner.id, "Plain")
    _, headers = _user(db_session, "lrn.h@example.com")
    assert client.get("/api/v1/discover/featured", headers=headers).json() == []


def test_featured_list(client, db_session):
    """UC-22: chỉ bộ is_featured + công khai mới lên khu vực nổi bật."""
    owner, _ = _user(db_session, "own.i@example.com")
    star = _public_set(db_session, owner.id, "Starred")
    star.is_featured = True
    hidden = _public_set(db_session, owner.id, "HiddenStar", is_public=False)
    hidden.is_featured = True
    _public_set(db_session, owner.id, "Normal")
    db_session.commit()

    _, headers = _user(db_session, "lrn.i@example.com")
    featured = client.get("/api/v1/discover/featured", headers=headers).json()
    assert [c["name"] for c in featured] == ["Starred"]
    assert featured[0]["is_featured"] is True and featured[0]["item_count"] == 5
