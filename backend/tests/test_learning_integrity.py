"""Regression cases for learning history, rewards, answer retries and local days."""
from datetime import datetime, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from app.models.base import Base

from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.session import StudySession
from app.models.user_progress import UserProgress
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.session import AnswerRequest
from app.schemas.session import SessionCreateRequest
from app.services import config_service, gamification_service, mastery_service, review_service, session_service, home_service
from test_gamification import _setup, _study


def _start(client, headers, ws, mode="flashcard"):
    response = client.post("/api/v1/sessions", headers=headers,
                           json={"word_set_id": ws.id, "mode": mode})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_answer_retry_is_once_even_after_completion(client, db_session, monkeypatch):
    user, headers, ws, items = _setup(db_session, "integrity.retry@example.com")
    sid = _start(client, headers, ws)
    payload = {"item_id": items[0].id, "is_correct": True, "client_answer_id": str(uuid4())}
    updates = []
    monkeypatch.setattr(mastery_service, "update_mastery_for_item", lambda *a, **k: updates.append(1))
    for _ in range(2):
        assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json=payload).status_code == 204
    first = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert first.status_code == 200
    assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json=payload).status_code == 204
    repeated = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert repeated.json() == first.json()
    assert db_session.query(Interaction).filter_by(session_id=sid).count() == 1
    assert len(updates) == 1
    assert db_session.query(UserProgress).filter_by(user_id=user.id).one().xp == first.json()["xp_earned"]
    payload["is_correct"] = False
    assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json=payload).status_code == 409


@pytest.mark.parametrize("mode,fmt", [("quiz", "quiz"), ("typing", "typing"),
    ("dictation", "dictation"), ("cloze", "cloze"), ("matching", "matching"),
    ("game_rain", "typing"), ("game_spelling", "dictation"), ("game_match", "matching"),
    ("mixed", "typing")])
def test_objective_answers_are_graded_by_server(client, db_session, mode, fmt):
    _, headers, ws, items = _setup(db_session, f"integrity.{mode}@example.com")
    sid = _start(client, headers, ws, mode)
    base = {"item_id": items[0].id, "is_correct": True, "exercise_format": fmt}
    assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json=base).status_code == 422
    for answer, claimed in [("incorrect", True),
                            (items[0].meaning if fmt in {"quiz", "matching"} else f" {items[0].word.upper()} ", False)]:
        response = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                               json={**base, "answer": answer, "is_correct": claimed})
        assert response.status_code == 204, response.text
    rows = db_session.execute(select(Interaction).where(Interaction.session_id == sid)
                               .order_by(Interaction.id)).scalars().all()
    assert [r.is_correct for r in rows] == [False, True]
    assert {r.exercise_format for r in rows} == {fmt}


def test_cannot_disguise_quiz_as_flashcard(client, db_session):
    _, headers, ws, items = _setup(db_session, "integrity.disguise@example.com")
    sid = _start(client, headers, ws, "quiz")
    response = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
        json={"item_id": items[0].id, "is_correct": True, "exercise_format": "flashcard"})
    assert response.status_code == 422


def test_abandoned_answers_do_not_consume_xp_and_history_is_kept(client, db_session):
    _, headers, ws, items = _setup(db_session, "integrity.abandon@example.com")
    sid = _start(client, headers, ws)
    for item, correct in zip(items, [True, False, True]):
        assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
            json={"item_id": item.id, "is_correct": correct}).status_code == 204
    assert client.post(f"/api/v1/sessions/{sid}/abandon", headers=headers).status_code == 204
    history = client.get("/api/v1/sessions/history", headers=headers).json()
    assert history["items"][0]["item_count"] == 3
    assert history["items"][0]["correct_count"] == 2
    assert history["total_items_answered"] == 3
    # Historical abandoned rows (before counters were added) remain readable.
    old = db_session.get(StudySession, sid)
    old.item_count = old.correct_count = None
    db_session.commit()
    legacy = client.get("/api/v1/sessions/history", headers=headers).json()
    assert legacy["items"][0]["item_count"] == legacy["total_items_answered"] == 3
    summary = _study(client, headers, ws.id, items, [True, True, True])
    assert summary["xp_earned"] == 3 * gamification_service.xp_per_correct()
    assert _study(client, headers, ws.id, items, [True, True, True])["xp_earned"] == 0


def test_failed_award_does_not_close_session(db_session, client, monkeypatch):
    user, headers, ws, items = _setup(db_session, "integrity.atomic@example.com")
    sid = _start(client, headers, ws)
    session_service.record_answer(db_session, user, sid, AnswerRequest(item_id=items[0].id, is_correct=True))
    original = gamification_service.award_session

    def broken(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("award transaction failed")

    with monkeypatch.context() as patch:
        patch.setattr(gamification_service, "award_session", broken)
        # Use a savepoint so the fixture's user/session survive the simulated
        # request rollback, exactly as they would in a separate prior request.
        with pytest.raises(RuntimeError), db_session.begin_nested():
            session_service.complete_session(db_session, user, sid)
    db_session.expire_all()
    assert db_session.get(StudySession, sid).status == "in_progress"
    assert db_session.query(UserProgress).filter_by(user_id=user.id).one().xp == 0
    assert session_service.complete_session(db_session, user, sid).xp_earned == gamification_service.xp_per_correct()


def test_mastered_requires_correct_answers_of_same_user_and_item(db_session, client, monkeypatch):
    user, headers, ws, items = _setup(db_session, "integrity.mastered@example.com")
    other, _, _, _ = _setup(db_session, "integrity.other@example.com")
    now = datetime.now(timezone.utc)
    db_session.add(KnowledgeState(user_id=user.id, item_id=items[0].id, mastery=0.95, last_updated=now))
    for _ in range(3):
        db_session.add(Interaction(user_id=other.id, item_id=items[0].id, is_correct=True, answered_at=now))
        db_session.add(Interaction(user_id=user.id, item_id=items[1].id, is_correct=True, answered_at=now))
    db_session.commit()
    assert mastery_service.mastered_item_ids(db_session, user.id) == set()
    for count in range(1, 4):
        db_session.add(Interaction(user_id=user.id, item_id=items[0].id, is_correct=True, answered_at=now))
        db_session.commit()
        expected = {items[0].id} if count == 3 else set()
        assert mastery_service.mastered_item_ids(db_session, user.id) == expected
        library = client.get(f"/api/v1/word-sets/{ws.id}", headers=headers).json()
        assert library["mastered_count"] == len(expected)
    monkeypatch.setitem(config_service._cache, "mastered_min_correct", 4)
    assert mastery_service.mastered_item_ids(db_session, user.id) == set()


def test_calendar_groups_by_local_day_at_utc_boundary(db_session, client, monkeypatch):
    user, _, _, items = _setup(db_session, "integrity.calendar@example.com")

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 7, 16, tzinfo=timezone.utc)  # 23:00 Vietnam

    monkeypatch.setattr(review_service, "datetime", FixedClock)
    times = [datetime(2026, 9, 7, 16, 30, tzinfo=timezone.utc),
             datetime(2026, 9, 7, 18, tzinfo=timezone.utc)]  # 01:00 next day
    for item, at in zip(items, times):
        db_session.add(ReviewSchedule(user_id=user.id, item_id=item.id, next_review_at=at, interval_days=1))
    db_session.commit()
    calendar = review_service.get_calendar(db_session, user)
    assert [x.item_id for x in calendar.today] == [items[0].id]
    assert [x.item_id for x in calendar.tomorrow] == [items[1].id]


def test_month_uses_learner_zone_and_includes_local_month_boundaries(db_session):
    user, _, _, items = _setup(db_session, "integrity.month@example.com")
    for item, at in zip(items, [
        datetime(2026, 4, 30, 18, tzinfo=timezone.utc),  # May 1 in Vietnam
        datetime(2026, 5, 31, 16, tzinfo=timezone.utc),  # May 31
        datetime(2026, 5, 31, 18, tzinfo=timezone.utc),  # June 1
    ]):
        db_session.add(ReviewSchedule(user_id=user.id, item_id=item.id, next_review_at=at, interval_days=1))
    db_session.commit()
    days = home_service.get_review_days(db_session, user, "2026-05")
    assert [str(day.date) for day in days] == ["2026-05-01", "2026-05-31"]
    settings = db_session.query(UserSettings).filter_by(user_id=user.id).one()
    settings.timezone = "America/New_York"
    db_session.commit()
    days = home_service.get_review_days(db_session, user, "2026-05")
    assert [(str(day.date), day.due_count) for day in days] == [("2026-05-31", 2)]


@pytest.fixture
def committed_engine():
    """Independent transactions need a disposable schema, not fixture savepoints."""
    from conftest import engine
    schema = f"integrity_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        yield isolated
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


@pytest.mark.parametrize("same_session", [True, False])
def test_concurrent_completions_award_each_item_once(same_session, monkeypatch, committed_engine):
    # Separate committed transactions are essential: a shared test Session
    # cannot reproduce row locking or two independent HTTP requests.
    engine = committed_engine
    monkeypatch.setattr(session_service.achievement_service, "check_and_unlock", lambda *a, **k: [])
    monkeypatch.setattr(session_service.level_up_service, "evaluate_after_session", lambda *a: None)
    with Session(engine, autoflush=False) as db:
        user, _, ws, items = _setup(db, f"integrity.concurrent.{same_session}@example.com")
        uid = user.id
        first = session_service.create_session(db, user, SessionCreateRequest(word_set_id=ws.id, mode="flashcard"))
        session_service.record_answer(db, user, first.id, AnswerRequest(item_id=items[0].id, is_correct=True))
        second_id = first.id
        if not same_session:
            second = session_service.create_session(db, user, SessionCreateRequest(mode="srs_review"))
            second_id = second.id
            session_service.record_answer(db, user, second.id, AnswerRequest(item_id=items[0].id, is_correct=True))
    gate = Barrier(2)

    def finish(sid):
        with Session(engine, autoflush=False) as db:
            learner = db.get(User, uid)
            gate.wait(timeout=10)
            return session_service.complete_session(db, learner, sid)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, [first.id, second_id]))
    with Session(engine) as db:
        progress = db.query(UserProgress).filter_by(user_id=uid).one()
        assert progress.xp == gamification_service.xp_per_correct()
    if same_session:
        assert results[0] == results[1]
    else:
        assert sum(r.xp_earned for r in results) == gamification_service.xp_per_correct()


def test_start_new_session_keeps_abandoned_answer_counts(client, db_session):
    _, headers, ws, items = _setup(db_session, "integrity.autoclose@example.com")
    old = _start(client, headers, ws)
    client.post(f"/api/v1/sessions/{old}/answer", headers=headers,
                json={"item_id": items[0].id, "is_correct": False})
    _start(client, headers, ws)
    row = db_session.get(StudySession, old)
    assert row.status == "abandoned" and row.item_count == 1 and row.correct_count == 0
