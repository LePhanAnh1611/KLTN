"""UC-34 — SM-2 baseline (4 nút Lại/Khó/Tốt/Dễ, lịch ôn cổ điển)."""
from app.core.security import create_access_token
from app.models.review_schedule import ReviewSchedule
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import dkt_client
from app.services.auth_service import register_user
from app.services.sm2_service import sm2_step


def _setup(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    item = Item(word_set_id=ws.id, word="boy", meaning="con trai")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return user, headers, ws, item


def _start(client, headers, ws_id):
    return client.post("/api/v1/sessions", json={"word_set_id": ws_id, "mode": "sm2"},
                       headers=headers).json()["id"]


def test_sm2_step_progression():
    # Tốt (q4) từ reps 0 -> interval 1; reps 1 -> 6; reps 2 -> interval*ease
    i, e, r = sm2_step(4, 1, 2.5, 0)
    assert i == 1 and r == 1
    i, e, r = sm2_step(4, i, e, r)
    assert i == 6 and r == 2
    i, e, r = sm2_step(4, i, e, r)
    assert i == round(6 * e) and r == 3


def test_sm2_again_resets():
    i, e, r = sm2_step(1, 20, 2.5, 5)  # Lại
    assert i == 1 and r == 0
    assert e < 2.5  # ease giảm khi quên


def test_sm2_easy_grows_ease():
    _, e_good, _ = sm2_step(4, 6, 2.5, 2)
    _, e_easy, _ = sm2_step(5, 6, 2.5, 2)
    assert e_easy > e_good  # Dễ tăng ease nhiều hơn Tốt


def test_answer_with_sm2_rating_schedules_sm2(client, db_session, monkeypatch):
    # DKT trả mastery thấp (0.3) nhưng có sm2_rating -> lịch theo SM-2 (Tốt), KHÔNG mastery-based
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.3 for x in t})
    user, headers, ws, item = _setup(db_session, "sm2.a@example.com")
    sid = _start(client, headers, ws.id)

    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": item.id, "is_correct": True, "sm2_rating": "good"}, headers=headers)
    assert r.status_code == 204

    rs = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=item.id).one()
    assert rs.interval_days == 1 and rs.repetitions == 1  # SM-2 Tốt lần đầu
    # nếu là mastery-based (0.3) thì interval cũng 1 nhưng repetitions vẫn phải =1 (SM-2 path)


def test_sm2_again_via_api(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.9 for x in t})
    user, headers, ws, item = _setup(db_session, "sm2.b@example.com")
    sid = _start(client, headers, ws.id)

    # Tốt 2 lần để tăng repetitions rồi Lại -> reset
    for _ in range(2):
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": item.id, "is_correct": True, "sm2_rating": "good"}, headers=headers)
    client.post(f"/api/v1/sessions/{sid}/answer",
                json={"item_id": item.id, "is_correct": False, "sm2_rating": "again"}, headers=headers)

    rs = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=item.id).one()
    assert rs.interval_days == 1 and rs.repetitions == 0  # Lại reset


def test_invalid_rating_rejected(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, item = _setup(db_session, "sm2.c@example.com")
    sid = _start(client, headers, ws.id)
    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": item.id, "is_correct": True, "sm2_rating": "maybe"}, headers=headers)
    assert r.status_code == 422
