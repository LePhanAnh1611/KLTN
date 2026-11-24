"""UC-40 — trang tiến độ (phân bố mastery + từ điểm yếu) + UC-42 tên bậc."""
from datetime import datetime, timezone

from app.core.security import create_access_token
from app.models.item import Item
from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.services.gamification_service import level_title


def _setup(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    words = ["a", "b", "c", "d", "e"]
    items = [Item(word_set_id=ws.id, word=w, meaning=f"m_{w}") for w in words]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def test_level_title():
    assert level_title(1) == "Người mới"
    assert level_title(3) == "Học viên"
    assert level_title(5) == "Chăm chỉ"
    assert level_title(7) == "Giỏi"
    assert level_title(10) == "Bậc thầy"


def test_progress_distribution_and_weak(client, db_session):
    user, headers, ws, items = _setup(db_session, "pp.a@example.com")
    now = datetime.now(timezone.utc)
    # mastery: 0.1(Mới) 0.45(Đang học) 0.7(Khá) 0.95(Đã thuộc) — item[4] chưa học
    masteries = [0.1, 0.45, 0.7, 0.95]
    db_session.add_all([
        Interaction(user_id=user.id, item_id=items[3].id, is_correct=True, answered_at=now)
        for _ in range(3)
    ])
    db_session.add_all([
        KnowledgeState(user_id=user.id, item_id=items[i].id, mastery=m, last_updated=now)
        for i, m in enumerate(masteries)
    ])
    db_session.commit()

    p = client.get("/api/v1/progress", headers=headers).json()
    assert p["total_items"] == 5
    assert p["learned_items"] == 4
    assert p["mastered_items"] == 1
    dist = {b["label"]: b["count"] for b in p["mastery_distribution"]}
    assert dist == {"Mới": 1, "Đang học": 1, "Khá": 1, "Đã thuộc": 1}
    # từ điểm yếu (mastery < 0.6), thấp nhất trước
    weak_words = [w["word"] for w in p["weak_items"]]
    assert weak_words == ["a", "b"]  # 0.1 rồi 0.45


def test_progress_level_title_from_xp(client, db_session):
    user, headers, _, _ = _setup(db_session, "pp.b@example.com")
    prog = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    prog.xp = 450  # level 5
    db_session.commit()

    p = client.get("/api/v1/progress", headers=headers).json()
    assert p["level"] == 5
    assert p["level_title"] == "Chăm chỉ"


def test_progress_empty_user(client, db_session):
    _, headers, _, _ = _setup(db_session, "pp.c@example.com")
    p = client.get("/api/v1/progress", headers=headers).json()
    assert p["learned_items"] == 0 and p["mastered_items"] == 0
    assert p["weak_items"] == []
    assert sum(b["count"] for b in p["mastery_distribution"]) == 0


def test_progress_requires_auth(client):
    assert client.get("/api/v1/progress").status_code == 401


def test_daily_xp_zero_before_study(client, db_session):
    """UC-41 E1: chưa học hôm nay -> 0 XP, chưa đạt mục tiêu."""
    from app.services.gamification_service import default_daily_xp_goal

    _, headers, _, _ = _setup(db_session, "pp.d@example.com")
    p = client.get("/api/v1/progress", headers=headers).json()
    assert p["today_xp"] == 0
    assert p["daily_xp_goal"] == default_daily_xp_goal()
    assert p["daily_goal_reached"] is False


def test_daily_xp_reflects_today_and_goal(client, db_session, monkeypatch):
    """UC-41: XP hôm nay = tổng xp_earned phiên completed hôm nay; đạt mục tiêu khi >= định mức."""
    from app.services import dkt_client
    from app.models.user_settings import UserSettings

    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "pp.e@example.com")
    settings = db_session.query(UserSettings).filter_by(user_id=user.id).one()
    settings.daily_xp_goal = 20
    db_session.commit()

    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    for it in items[:3]:  # 3 đúng -> 30 XP
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": it.id, "is_correct": True}, headers=headers)
    client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)

    p = client.get("/api/v1/progress", headers=headers).json()
    assert p["today_xp"] == 30
    assert p["daily_xp_goal"] == 20
    assert p["daily_goal_reached"] is True
