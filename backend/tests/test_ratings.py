"""UC-23 — đánh giá / xếp hạng bộ từ công khai."""
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


def _public_set(db_session, owner_id, name, n_items=3):
    ws = WordSet(owner_id=owner_id, name=name, is_public=True)
    db_session.add(ws)
    db_session.flush()
    db_session.add_all([Item(word_set_id=ws.id, word=f"{name}_w{i}", meaning=f"m{i}") for i in range(n_items)])
    db_session.commit()
    db_session.refresh(ws)
    return ws


def test_rate_requires_download(client, db_session):
    """E1: chưa tải bộ từ thì không được đánh giá (chống spam)."""
    owner, _ = _user(db_session, "rt.own1@example.com")
    ws = _public_set(db_session, owner.id, "Animals")
    _, headers = _user(db_session, "rt.lrn1@example.com")

    r = client.put(f"/api/v1/discover/{ws.id}/rating", json={"stars": 5}, headers=headers)
    assert r.status_code == 403

    summary = client.get(f"/api/v1/discover/{ws.id}/ratings", headers=headers).json()
    assert summary["can_rate"] is False
    assert summary["count"] == 0 and summary["average"] is None


def test_rate_then_update(client, db_session):
    """Luồng chính + 1a: chấm sao rồi sửa lại — vẫn chỉ 1 đánh giá/người/bộ."""
    owner, _ = _user(db_session, "rt.own2@example.com")
    ws = _public_set(db_session, owner.id, "Food")
    _, headers = _user(db_session, "rt.lrn2@example.com")
    client.post(f"/api/v1/discover/{ws.id}/download", headers=headers)

    r = client.put(f"/api/v1/discover/{ws.id}/rating",
                   json={"stars": 5, "comment": "Bộ từ hay"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["average"] == 5.0 and r.json()["count"] == 1

    r = client.put(f"/api/v1/discover/{ws.id}/rating", json={"stars": 3}, headers=headers)
    body = r.json()
    assert body["count"] == 1  # sửa, không tạo thêm
    assert body["average"] == 3.0
    assert body["my_stars"] == 3 and body["my_comment"] is None


def test_rating_average_across_users_and_sort(client, db_session):
    """Điểm TB gộp nhiều người + sort=rating xếp bộ điểm cao lên trước."""
    owner, _ = _user(db_session, "rt.own3@example.com")
    good = _public_set(db_session, owner.id, "Good set")
    meh = _public_set(db_session, owner.id, "Meh set")

    for i, (stars_good, stars_meh) in enumerate([(5, 2), (4, 1)]):
        _, headers = _user(db_session, f"rt.lrn3{i}@example.com")
        client.post(f"/api/v1/discover/{good.id}/download", headers=headers)
        client.post(f"/api/v1/discover/{meh.id}/download", headers=headers)
        client.put(f"/api/v1/discover/{good.id}/rating", json={"stars": stars_good}, headers=headers)
        client.put(f"/api/v1/discover/{meh.id}/rating", json={"stars": stars_meh}, headers=headers)

    _, viewer = _user(db_session, "rt.view3@example.com")
    summary = client.get(f"/api/v1/discover/{good.id}/ratings", headers=viewer).json()
    assert summary["average"] == 4.5 and summary["count"] == 2
    assert summary["my_stars"] is None

    items = client.get("/api/v1/discover?sort=rating", headers=viewer).json()["items"]
    names = [c["name"] for c in items]
    assert names.index("Good set") < names.index("Meh set")
    card = next(c for c in items if c["name"] == "Good set")
    assert card["rating_avg"] == 4.5 and card["rating_count"] == 2


def test_rating_shown_in_detail(client, db_session):
    owner, _ = _user(db_session, "rt.own4@example.com")
    ws = _public_set(db_session, owner.id, "Travel")
    _, headers = _user(db_session, "rt.lrn4@example.com")
    client.post(f"/api/v1/discover/{ws.id}/download", headers=headers)
    client.put(f"/api/v1/discover/{ws.id}/rating", json={"stars": 4}, headers=headers)

    detail = client.get(f"/api/v1/discover/{ws.id}", headers=headers).json()
    assert detail["rating_avg"] == 4.0 and detail["rating_count"] == 1


def test_rate_invalid_stars_and_hidden_set(client, db_session):
    owner, _ = _user(db_session, "rt.own5@example.com")
    ws = _public_set(db_session, owner.id, "Sports")
    _, headers = _user(db_session, "rt.lrn5@example.com")
    client.post(f"/api/v1/discover/{ws.id}/download", headers=headers)

    assert client.put(f"/api/v1/discover/{ws.id}/rating", json={"stars": 6}, headers=headers).status_code == 422

    ws.is_public = False
    db_session.commit()
    assert client.get(f"/api/v1/discover/{ws.id}/ratings", headers=headers).status_code == 404
