"""UC-64 — cập nhật KNOWLEDGE_STATE sau mỗi câu (mock service DKT để test hermetic)."""
from app.core.security import create_access_token
from app.models.interaction import Interaction
from app.models.item import Item
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
    items = [Item(word_set_id=ws.id, word=w, meaning=f"n_{w}", part_of_speech="noun")
             for w in ("boy", "girl", "water")]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _start(client, headers, ws_id) -> int:
    r = client.post("/api/v1/sessions", json={"word_set_id": ws_id, "mode": "flashcard"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def test_answer_updates_mastery(client, db_session, monkeypatch):
    # mock service DKT: trả mastery cố định theo từ
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda hist, targets, **kwargs: {t: 0.83 for t in targets})
    user, headers, ws, items = _setup(db_session, "ks.a@example.com")
    sid = _start(client, headers, ws.id)

    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": True}, headers=headers)
    assert r.status_code == 204

    ks = db_session.query(KnowledgeState).filter_by(user_id=user.id, item_id=items[0].id).one()
    assert abs(ks.mastery - 0.83) < 1e-6
    assert ks.last_updated is not None


def test_answer_upserts_not_duplicate(client, db_session, monkeypatch):
    vals = iter([0.5, 0.9])
    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda hist, targets, **kwargs: {t: next(vals) for t in targets})
    user, headers, ws, items = _setup(db_session, "ks.b@example.com")
    sid = _start(client, headers, ws.id)

    for correct in (False, True):
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": correct}, headers=headers)

    rows = db_session.query(KnowledgeState).filter_by(user_id=user.id, item_id=items[0].id).all()
    assert len(rows) == 1              # upsert, không nhân bản
    assert abs(rows[0].mastery - 0.9) < 1e-6  # giá trị mới nhất


def test_none_mastery_cold_start_prior(client, db_session, monkeypatch):
    # từ ngoài vocab -> DKT None -> UC-69 cold-start: đặt prior theo độ khó bộ (beginner=0.6)
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda hist, targets, **kwargs: {t: None for t in targets})
    user, headers, ws, items = _setup(db_session, "ks.c@example.com")  # difficulty=beginner
    sid = _start(client, headers, ws.id)

    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": True}, headers=headers)
    assert r.status_code == 204

    ks = db_session.query(KnowledgeState).filter_by(user_id=user.id, item_id=items[0].id).one()
    assert abs(ks.mastery - 0.6) < 1e-6  # prior beginner
    assert db_session.query(Interaction).filter_by(session_id=sid).count() == 1  # BR-05


def test_cold_start_does_not_overwrite_existing(client, db_session, monkeypatch):
    # đã có mastery thật -> lần sau DKT None (service lỗi) KHÔNG ghi đè bằng prior
    # Mỗi lượt gọi DKT HAI lần: dự đoán trước khi ghi (UC-70) rồi cập nhật sau.
    seq = iter([0.7, 0.85, 0.7, None])
    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda hist, targets, **kwargs: {t: next(seq) for t in targets})
    user, headers, ws, items = _setup(db_session, "ks.f@example.com")
    sid = _start(client, headers, ws.id)

    for correct in (True, True):
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": correct}, headers=headers)

    ks = db_session.query(KnowledgeState).filter_by(user_id=user.id, item_id=items[0].id).one()
    assert abs(ks.mastery - 0.85) < 1e-6  # giữ giá trị DKT thật, không bị prior đè


def test_cold_start_prior_by_difficulty():
    from app.services.mastery_service import cold_start_prior
    assert cold_start_prior("beginner") == 0.6
    assert cold_start_prior("intermediate") == 0.5
    assert cold_start_prior("advanced") == 0.4
    assert cold_start_prior(None) == 0.5  # mặc định
    assert cold_start_prior("unknown-level") == 0.5


def test_service_error_does_not_break_answer(client, db_session, monkeypatch):
    def boom(hist, targets):
        raise RuntimeError("service down")
    monkeypatch.setattr(dkt_client, "predict_mastery", boom)
    user, headers, ws, items = _setup(db_session, "ks.d@example.com")
    sid = _start(client, headers, ws.id)

    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": True}, headers=headers)
    assert r.status_code == 204  # câu vẫn thành công
    assert db_session.query(Interaction).filter_by(session_id=sid).count() == 1
    assert db_session.query(KnowledgeState).filter_by(user_id=user.id).count() == 0


def test_history_time_order(db_session):
    # build_history trả đúng thứ tự thời gian tăng dần (không cần service DKT)
    from datetime import datetime, timedelta, timezone

    from app.services.mastery_service import build_history

    user, _, ws, items = _setup(db_session, "ks.e@example.com")
    base = datetime.now(timezone.utc)
    formats = ["quiz", "typing", "dictation"]
    for k, (it, c) in enumerate([(items[0], 1), (items[1], 0), (items[2], 1)]):
        db_session.add(Interaction(user_id=user.id, item_id=it.id, is_correct=bool(c),
                                   exercise_format=formats[k],
                                   answered_at=base + timedelta(seconds=k)))
    db_session.commit()

    history, history_formats, history_pos = build_history(db_session, user.id)
    assert history == [("boy", 1), ("girl", 0), ("water", 1)]
    # Dạng bài phải đi SONG SONG và cùng thứ tự với lịch sử: lệch một nhịp là
    # mô hình đọc dạng bài của lượt khác mà không có dấu hiệu gì báo ra.
    assert history_formats == formats
    # Từ loại phải kèm theo cho CẢ lịch sử, không riêng từ đang chấm: thiếu nó
    # làm AUC tụt 8 điểm mà không có lỗi nào hiện ra.
    assert history_pos == {"boy": "noun", "girl": "noun", "water": "noun"}


# --- UC-70: dự đoán được chốt NGAY TRƯỚC lượt trả lời (đổi 2026-10-13) ---------

def _start_mixed(client, headers, ws_id) -> int:
    r = client.post("/api/v1/sessions", json={"word_set_id": ws_id, "mode": "mixed"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def test_prediction_uses_history_before_answer_and_current_format(client, db_session, monkeypatch):
    """Dự đoán ghi vào INTERACTION phải là câu trả lời TƯƠI của mô hình:
    lịch sử chưa gồm lượt hiện tại, dạng bài là dạng bài của lượt hiện tại —
    không phải giá trị KNOWLEDGE_STATE còn sót lại từ lần gặp trước."""
    calls = []

    def fake(hist, targets, **kwargs):
        calls.append({"hist": list(hist), "target_format": kwargs.get("target_format")})
        return {t: 0.1 * len(calls) for t in targets}  # mỗi lần gọi một số khác nhau

    monkeypatch.setattr(dkt_client, "predict_mastery", fake)
    user, headers, ws, items = _setup(db_session, "ks.pred@example.com")
    boy, girl = items[0], items[1]
    sid = _start_mixed(client, headers, ws.id)

    def answer(item, fmt, value):
        r = client.post(f"/api/v1/sessions/{sid}/answer",
                        json={"item_id": item.id, "exercise_format": fmt, "answer": value},
                        headers=headers)
        assert r.status_code == 204

    answer(boy, "quiz", boy.meaning)        # gọi 1 (trước) + 2 (cập nhật)
    answer(girl, "quiz", "sai")             # gọi 3 + 4
    answer(boy, "typing", "boy")            # gọi 5 (trước) + 6

    rows = (db_session.query(Interaction).filter_by(session_id=sid)
            .order_by(Interaction.id).all())

    # Lần gặp ĐẦU vẫn có dự đoán (bản feature-based chấm được từ chưa gặp).
    assert rows[0].prediction_source == "model"
    assert abs(rows[0].predicted_mastery - 0.1) < 1e-6
    assert calls[0]["hist"] == []

    # Lần gặp lại "boy": lịch sử gồm 2 lượt trước (cả từ khác), KHÔNG gồm lượt này,
    # và dạng bài là "typing" của lượt này chứ không phải "quiz" của lần trước.
    assert calls[4]["hist"] == [("boy", 1), ("girl", 0)]
    assert calls[4]["target_format"] == "typing"
    assert abs(rows[2].predicted_mastery - 0.5) < 1e-6
    # ...và KHÁC giá trị đang lưu cho "boy" lúc đó (0.2, tính sau lượt 1).
    assert abs(rows[2].predicted_mastery - 0.2) > 1e-6


def test_prediction_missing_when_service_down(client, db_session, monkeypatch):
    """Service không trả số -> không ghi dự đoán (không rơi về prior), và câu trả
    lời vẫn được ghi đầy đủ (BR-05)."""
    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda hist, targets, **kwargs: {t: None for t in targets})
    user, headers, ws, items = _setup(db_session, "ks.down@example.com")
    sid = _start(client, headers, ws.id)
    for _ in range(2):
        r = client.post(f"/api/v1/sessions/{sid}/answer",
                        json={"item_id": items[0].id, "is_correct": True}, headers=headers)
        assert r.status_code == 204
    rows = db_session.query(Interaction).filter_by(session_id=sid).all()
    assert len(rows) == 2
    assert all(r.predicted_mastery is None and r.prediction_source is None for r in rows)


def test_prediction_error_does_not_break_answer(client, db_session, monkeypatch):
    def boom(hist, targets, **kwargs):
        raise RuntimeError("ml-serve exploded")
    monkeypatch.setattr(dkt_client, "predict_mastery", boom)
    user, headers, ws, items = _setup(db_session, "ks.boom@example.com")
    sid = _start(client, headers, ws.id)
    r = client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": items[0].id, "is_correct": True}, headers=headers)
    assert r.status_code == 204
    row = db_session.query(Interaction).filter_by(session_id=sid).one()
    assert row.predicted_mastery is None
