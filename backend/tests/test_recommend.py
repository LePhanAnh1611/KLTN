"""UC-65 — gợi ý item vừa sức P(đúng) ∈ [0.6, 0.8] (mock DKT)."""
from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service, dkt_client
from app.services.auth_service import register_user


def _setup(db_session, email: str, difficulty="beginner"):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty=difficulty)
    db_session.add(ws)
    db_session.flush()
    words = ["easy1", "easy2", "mid1", "mid2", "hard1"]
    items = [Item(word_set_id=ws.id, word=w, meaning=f"n_{w}") for w in words]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, {it.word: it for it in items}


def test_recommend_prefers_in_band(client, db_session, monkeypatch):
    # kiểm tra riêng luật BR-03 -> tắt thăm dò ngẫu nhiên của pilot
    config_service._cache = {"explore_rate": "0"}
    # mastery: easy quá cao (0.95), hard quá thấp (0.3), mid vừa sức (0.7/0.65)
    mp = {"easy1": 0.95, "easy2": 0.92, "mid1": 0.70, "mid2": 0.65, "hard1": 0.30}
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: mp[x] for x in t})
    _, headers, ws, _ = _setup(db_session, "rec.a@example.com")

    res = client.get(f"/api/v1/word-sets/{ws.id}/recommend?limit=2", headers=headers).json()
    words = [r["word"] for r in res]
    assert words == ["mid1", "mid2"]        # vừa sức, mid1 gần 0.7 nhất
    assert all(r["in_band"] for r in res)


def test_recommend_relax_when_not_enough(client, db_session, monkeypatch):
    # kiểm tra riêng luật BR-03 -> tắt thăm dò ngẫu nhiên của pilot
    config_service._cache = {"explore_rate": "0"}
    # chỉ 1 item vừa sức -> phải bù thêm item gần vùng nhất (UC-27 E1)
    mp = {"easy1": 0.95, "easy2": 0.92, "mid1": 0.70, "mid2": 0.85, "hard1": 0.30}
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: mp[x] for x in t})
    _, headers, ws, _ = _setup(db_session, "rec.b@example.com")

    res = client.get(f"/api/v1/word-sets/{ws.id}/recommend?limit=3", headers=headers).json()
    assert len(res) == 3
    assert res[0]["word"] == "mid1" and res[0]["in_band"] is True
    # 2 item bù là gần vùng nhất: mid2 (0.85, cách 0.05) rồi easy2 (0.92, cách 0.12)
    assert [r["word"] for r in res[1:]] == ["mid2", "easy2"]
    assert all(r["in_band"] is False for r in res[1:])


def test_recommend_out_of_vocab_uses_prior(client, db_session, monkeypatch):
    # DKT None hết -> prior beginner 0.6 (in-band) cho mọi item
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: None for x in t})
    _, headers, ws, _ = _setup(db_session, "rec.c@example.com", difficulty="beginner")

    res = client.get(f"/api/v1/word-sets/{ws.id}/recommend", headers=headers).json()
    assert len(res) == 5
    assert all(abs(r["mastery"] - 0.6) < 1e-6 and r["in_band"] for r in res)


def test_recommend_empty_set(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {})
    user = register_user(
        db_session,
        RegisterRequest(email="rec.d@example.com", password="Abcd1234",
                        password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Empty", category="Gen", difficulty="beginner")
    db_session.add(ws); db_session.commit(); db_session.refresh(ws)

    assert client.get(f"/api/v1/word-sets/{ws.id}/recommend", headers=headers).json() == []


def test_recommend_ownership_and_auth(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {})
    _, headers_a, ws, _ = _setup(db_session, "rec.owner@example.com")
    _, headers_b, _, _ = _setup(db_session, "rec.other@example.com")

    assert client.get(f"/api/v1/word-sets/{ws.id}/recommend", headers=headers_b).status_code == 404
    assert client.get(f"/api/v1/word-sets/{ws.id}/recommend").status_code == 401
