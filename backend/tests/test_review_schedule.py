"""UC-66 — lập lịch ôn từ mastery (mock DKT)."""
from datetime import datetime, timezone

from app.core.security import create_access_token
from app.models.review_schedule import ReviewSchedule
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import dkt_client
from app.services.auth_service import register_user
from app.services.review_service import mastery_to_interval_days


def _setup(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=w, meaning=f"n_{w}") for w in ("boy", "girl")]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _start(client, headers, ws_id) -> int:
    r = client.post("/api/v1/sessions", json={"word_set_id": ws_id, "mode": "flashcard"}, headers=headers)
    return r.json()["id"]


def test_interval_mapping():
    assert mastery_to_interval_days(0.3) == 1   # < θ_review
    assert mastery_to_interval_days(0.6) == 2
    assert mastery_to_interval_days(0.8) == 4
    assert mastery_to_interval_days(0.95) == 7  # đã thuộc -> thưa


def test_answer_creates_review_schedule(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    user, headers, ws, items = _setup(db_session, "rv.a@example.com")
    sid = _start(client, headers, ws.id)

    client.post(f"/api/v1/sessions/{sid}/answer",
                json={"item_id": items[0].id, "is_correct": True}, headers=headers)

    rs = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=items[0].id).one()
    # Luật mới (UC-66 bản sửa): mới gặp MỘT lần thì dù DKT chấm 0,95 lịch vẫn
    # chỉ đặt ở ngày mai — chưa có bằng chứng nào cho thấy nó sống qua một tuần.
    # Luật cũ nhảy thẳng lên 7 ngày ở đây, và đó đúng là kiểu giãn quá tay đã
    # thua SM-2 trong thí nghiệm UC-93.
    assert rs.interval_days == 1
    assert rs.half_life_days is not None
    assert rs.next_review_at > datetime.now(timezone.utc)


def test_interval_gian_dan_qua_cac_luot_dung(client, db_session, monkeypatch):
    """Giãn phải đến TỪ LỊCH SỬ, không phải từ một con số mastery đơn lẻ."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    user, headers, ws, items = _setup(db_session, "rv.a2@example.com")
    seen = []
    for _ in range(5):
        sid = _start(client, headers, ws.id)
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": True}, headers=headers)
        db_session.expire_all()
        seen.append(db_session.query(ReviewSchedule).filter_by(
            user_id=user.id, item_id=items[0].id).one().interval_days)

    assert seen == sorted(seen), f"khoảng cách phải tăng dần, nhận được {seen}"
    assert seen[-1] > seen[0]


def test_low_mastery_short_interval(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.4 for x in t})
    user, headers, ws, items = _setup(db_session, "rv.b@example.com")
    sid = _start(client, headers, ws.id)

    client.post(f"/api/v1/sessions/{sid}/answer",
                json={"item_id": items[0].id, "is_correct": False}, headers=headers)

    rs = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=items[0].id).one()
    assert rs.interval_days == 1  # mastery thấp -> ôn ngày mai


def test_review_schedule_upsert(client, db_session, monkeypatch):
    vals = iter([0.95, 0.4])
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: next(vals) for x in t})
    user, headers, ws, items = _setup(db_session, "rv.c@example.com")
    sid = _start(client, headers, ws.id)

    for correct in (True, False):
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": correct}, headers=headers)

    rows = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=items[0].id).all()
    assert len(rows) == 1              # upsert
    assert rows[0].interval_days == 1  # cập nhật theo mastery mới nhất (0.4)


def test_dashboard_review_due_reflects_schedule(client, db_session, monkeypatch):
    # lịch ôn đến hạn (quá khứ) -> dashboard đếm được (khôi phục backlog)
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    user, headers, ws, items = _setup(db_session, "rv.d@example.com")
    sid = _start(client, headers, ws.id)
    client.post(f"/api/v1/sessions/{sid}/answer",
                json={"item_id": items[0].id, "is_correct": True}, headers=headers)

    # ép next_review_at về quá khứ để thành "đến hạn"
    rs = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=items[0].id).one()
    rs.next_review_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()

    body = client.get("/api/v1/dashboard", headers=headers).json()
    assert body["review_due_count"] == 1
