"""UC-48 mở khóa huy hiệu + UC-43 xem huy hiệu (mock DKT)."""
from app.core.security import create_access_token
from app.models.item import Item
from app.models.user_achievement import UserAchievement
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import achievement_service, dkt_client
from app.services.auth_service import register_user


def _setup(db_session, email: str, n_items=3):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"w{i}", meaning=f"m{i}") for i in range(n_items)]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _study(client, headers, ws_id, items, correct=True):
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws_id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    for it in items:
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": it.id, "is_correct": correct}, headers=headers)
    return client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()


def test_first_session_unlocks(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "ach.a@example.com")
    summary = _study(client, headers, ws.id, items[:1])
    assert "Bước đầu tiên" in summary["new_achievements"]
    assert db_session.query(UserAchievement).filter_by(user_id=user.id).count() >= 1


def test_xp_100_achievement(client, db_session, monkeypatch):
    # 10 câu đúng = 100 XP -> mở "Tân binh"
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, _ = _setup(db_session, "ach.b@example.com", n_items=10)
    items = client.get(f"/api/v1/word-sets/{ws.id}/items", headers=headers).json()
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    for it in items:
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": it["id"], "is_correct": True}, headers=headers)
    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()
    assert "Tân binh" in summary["new_achievements"]


def test_achievement_not_duplicated(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "ach.c@example.com")
    _study(client, headers, ws.id, items[:1])
    summary2 = _study(client, headers, ws.id, items[1:2])
    # "Bước đầu tiên" đã mở ở phiên 1 -> không lặp ở phiên 2
    assert "Bước đầu tiên" not in summary2["new_achievements"]
    codes = [r.achievement_code for r in db_session.query(UserAchievement).filter_by(user_id=user.id).all()]
    assert codes.count("first_session") == 1


def test_list_achievements_status(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, items = _setup(db_session, "ach.d@example.com")
    _study(client, headers, ws.id, items[:1])

    res = client.get("/api/v1/achievements", headers=headers).json()
    assert len(res) == len(achievement_service.DEFAULT_ACHIEVEMENTS)
    first = next(a for a in res if a["code"] == "first_session")
    assert first["unlocked"] is True and first["unlocked_at"] is not None
    locked = next(a for a in res if a["code"] == "streak_7")
    assert locked["unlocked"] is False


def test_achievements_require_auth(client):
    assert client.get("/api/v1/achievements").status_code == 401
