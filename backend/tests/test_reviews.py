"""UC-36 lịch ôn tuần + UC-33 ôn SRS (mock DKT)."""
from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.item import Item
from app.models.review_schedule import ReviewSchedule
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import dkt_client
from app.services.auth_service import register_user


def _setup(db_session, email: str, n_sets: int = 1):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    sets = []
    for s in range(n_sets):
        ws = WordSet(owner_id=user.id, name=f"Set{s}", category="Gen", difficulty="beginner")
        db_session.add(ws)
        db_session.flush()
        items = [Item(word_set_id=ws.id, word=f"w{s}_{i}", meaning=f"m{s}_{i}") for i in range(3)]
        db_session.add_all(items)
        db_session.commit()
        for it in items:
            db_session.refresh(it)
        sets.append((ws, items))
    return user, headers, sets


def _schedule(db_session, user_id, item_id, days_from_now: int):
    at = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    db_session.add(ReviewSchedule(user_id=user_id, item_id=item_id, next_review_at=at,
                                  interval_days=max(days_from_now, 1)))
    db_session.commit()


def test_calendar_buckets(client, db_session):
    user, headers, sets = _setup(db_session, "rvw.a@example.com")
    _, items = sets[0]
    _schedule(db_session, user.id, items[0].id, -1)  # quá hạn -> today
    _schedule(db_session, user.id, items[1].id, 1)   # tomorrow
    _schedule(db_session, user.id, items[2].id, 5)   # this_week

    cal = client.get("/api/v1/reviews/calendar", headers=headers).json()
    assert [i["word"] for i in cal["today"]] == ["w0_0"]
    assert [i["word"] for i in cal["tomorrow"]] == ["w0_1"]
    assert [i["word"] for i in cal["this_week"]] == ["w0_2"]
    assert cal["today"][0]["word_set_name"] == "Set0"


def test_due_across_word_sets(client, db_session):
    user, headers, sets = _setup(db_session, "rvw.b@example.com", n_sets=2)
    _schedule(db_session, user.id, sets[0][1][0].id, -1)  # due, set0
    _schedule(db_session, user.id, sets[1][1][0].id, -2)  # due, set1
    _schedule(db_session, user.id, sets[0][1][1].id, 3)   # chưa đến hạn

    due = client.get("/api/v1/reviews/due", headers=headers).json()
    words = {d["word"] for d in due}
    assert words == {"w0_0", "w1_0"}  # xuyên 2 bộ, chỉ item đến hạn


def test_srs_session_answer_across_sets(client, db_session, monkeypatch):
    # phiên srs không gắn bộ -> trả lời item từ bất kỳ bộ user sở hữu
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    user, headers, sets = _setup(db_session, "rvw.c@example.com", n_sets=2)
    sid = client.post("/api/v1/sessions", json={"mode": "srs_review"}, headers=headers).json()["id"]

    r1 = client.post(f"/api/v1/sessions/{sid}/answer",
                     json={"item_id": sets[0][1][0].id, "is_correct": True}, headers=headers)
    r2 = client.post(f"/api/v1/sessions/{sid}/answer",
                     json={"item_id": sets[1][1][0].id, "is_correct": True}, headers=headers)
    assert r1.status_code == 204 and r2.status_code == 204


def test_srs_session_rejects_foreign_item(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers_a, _ = _setup(db_session, "rvw.owner@example.com")
    _, _, sets_b = _setup(db_session, "rvw.other@example.com")
    sid = client.post("/api/v1/sessions", json={"mode": "srs_review"}, headers=headers_a).json()["id"]

    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": sets_b[0][1][0].id, "is_correct": True}, headers=headers_a)
    assert r.status_code == 404  # item của user khác


def test_non_srs_requires_word_set(client, db_session):
    _, headers, _ = _setup(db_session, "rvw.d@example.com")
    r = client.post("/api/v1/sessions", json={"mode": "flashcard"}, headers=headers)
    assert r.status_code == 422  # thiếu word_set_id cho mode thường


def test_reviews_require_auth(client):
    assert client.get("/api/v1/reviews/calendar").status_code == 401
    assert client.get("/api/v1/reviews/due").status_code == 401
    assert client.post("/api/v1/reviews/pause-lower-level").status_code == 401


def test_daily_plan_uses_dkt_and_spreads_backlog(client, db_session, monkeypatch):
    from app.services import config_service
    config_service.set_values(db_session, {"review_daily_limit": 2})
    user, headers, sets = _setup(db_session, "rvw.plan@example.com", n_sets=2)
    items = [it for _, group in sets for it in group]
    for item in items:
        _schedule(db_session, user.id, item.id, -2)
    values = {item.word: (6 - index) / 10 for index, item in enumerate(items)}
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kw: values)
    cal = client.get("/api/v1/reviews/calendar", headers=headers).json()
    assert [it["item_id"] for it in cal["today"]] == [items[-1].id, items[-2].id]
    assert len(cal["tomorrow"]) == 2 and len(cal["this_week"]) == 2
    assert cal["backlog_count"] == 4 and cal["daily_limit"] == 2
    due = client.get("/api/v1/reviews/due?limit=200", headers=headers).json()
    assert due == cal["today"]  # API limit cannot bypass daily cap
    assert all(it["at_risk"] for it in due)
    assert all(rs.next_review_at < datetime.now(timezone.utc) for rs in db_session.query(ReviewSchedule).all())


def test_reviewed_today_consumes_daily_budget(client, db_session):
    from app.services import config_service
    config_service.set_values(db_session, {"review_daily_limit": 1})
    user, headers, sets = _setup(db_session, "rvw.budget@example.com")
    for item in sets[0][1]:
        _schedule(db_session, user.id, item.id, -1)
    item = client.get("/api/v1/reviews/due", headers=headers).json()[0]
    sid = client.post("/api/v1/sessions", json={"mode": "srs_review"}, headers=headers).json()["id"]
    assert client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": item["item_id"], "is_correct": True}, headers=headers).status_code == 204
    cal = client.get("/api/v1/reviews/calendar", headers=headers).json()
    assert cal["reviewed_today"] == 1 and cal["today"] == []
    assert cal["backlog_count"] == 2
    assert client.get("/api/v1/reviews/due", headers=headers).json() == []


def test_pause_lower_reviews_keeps_history_and_other_users(client, db_session):
    from app.models.user_settings import UserSettings
    from app.models.knowledge_state import KnowledgeState
    user, headers, sets = _setup(db_session, "rvw.pause@example.com", n_sets=2)
    other, _, others = _setup(db_session, "rvw.pause.other@example.com")
    db_session.query(UserSettings).filter_by(user_id=user.id).one().entry_cefr_level = "C1"
    sets[0][0].cefr_level = "A1"
    sets[1][0].cefr_level = "C1"
    for _, items in sets + others:
        for item in items:
            owner = user if item in sets[0][1] + sets[1][1] else other
            _schedule(db_session, owner.id, item.id, -1)
    db_session.add(KnowledgeState(user_id=user.id, item_id=sets[0][1][0].id, mastery=0.2, last_updated=datetime.now(timezone.utc)))
    db_session.commit()
    assert client.post("/api/v1/reviews/pause-lower-level", headers=headers).json() == {"paused_count": 3}
    assert client.post("/api/v1/reviews/pause-lower-level", headers=headers).json() == {"paused_count": 0}
    assert {it["word_set_id"] for it in client.get("/api/v1/reviews/due", headers=headers).json()} == {sets[1][0].id}
    assert client.get("/api/v1/reviews/weak", headers=headers).json() == []
    assert db_session.query(KnowledgeState).filter_by(user_id=user.id).one().mastery == 0.2
    assert not any(rs.is_paused for rs in db_session.query(ReviewSchedule).filter_by(user_id=other.id))
