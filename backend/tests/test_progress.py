"""UC-16 tiến độ học (mastered_count ở thư viện) + UC-30 item mới đạt thuộc (BR-01)."""
from datetime import datetime, timezone

from app.core.security import create_access_token
from app.models.item import Item
from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import dkt_client
from app.services.auth_service import register_user


def _setup(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"w{i}", meaning=f"m{i}") for i in range(3)]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def test_library_mastered_count(client, db_session):
    # 3 từ: 2 mastery>=0.9 (đã thuộc), 1 dưới ngưỡng
    user, headers, ws, items = _setup(db_session, "prg.a@example.com")
    now = datetime.now(timezone.utc)
    db_session.add_all([
        KnowledgeState(user_id=user.id, item_id=items[0].id, mastery=0.95, last_updated=now),
        KnowledgeState(user_id=user.id, item_id=items[1].id, mastery=0.91, last_updated=now),
        KnowledgeState(user_id=user.id, item_id=items[2].id, mastery=0.5, last_updated=now),
    ])
    db_session.add_all([
        Interaction(user_id=user.id, item_id=it.id, is_correct=True, answered_at=now)
        for it in items for _ in range(3)
    ])
    db_session.commit()

    lib = client.get("/api/v1/word-sets", headers=headers).json()
    card = next(s for s in lib if s["id"] == ws.id)
    assert card["item_count"] == 3
    assert card["mastered_count"] == 2  # đủ 3 lần đúng, vẫn phải đạt ngưỡng mastery


def test_library_mastered_count_zero_initially(client, db_session):
    _, headers, ws, _ = _setup(db_session, "prg.b@example.com")
    card = client.get(f"/api/v1/word-sets/{ws.id}", headers=headers).json()
    assert card["mastered_count"] == 0


def test_summary_mastered_count(client, db_session, monkeypatch):
    # Mỗi từ đúng 3 lần và mastery 0.95 mới được công nhận đã thuộc.
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    _, headers, ws, items = _setup(db_session, "prg.c@example.com")
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    for it in items[:2] * 3:
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": it.id, "is_correct": True}, headers=headers)

    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()
    assert summary["total_answered"] == 6
    assert summary["mastered_count"] == 2


def test_summary_mastered_count_below_threshold(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, items = _setup(db_session, "prg.d@example.com")
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/answer",
                json={"item_id": items[0].id, "is_correct": False}, headers=headers)

    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()
    assert summary["mastered_count"] == 0  # mastery 0.5 < 0.9
