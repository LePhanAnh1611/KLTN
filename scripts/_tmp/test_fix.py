"""Sự cố chấm sai 2026-10-26: cờ loại trừ + script sửa dữ liệu."""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.session import StudySession
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.schemas.session import AnswerRequest
from app.scripts import fix_grading_bug_20261026 as fixmod
from app.services import dkt_client
from app.services.auth_service import register_user
from app.services.mastery_service import build_history

T0 = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)  # trong khoảng lỗi


def _world(db):
    user = register_user(db, RegisterRequest(email="bug@example.com", password="Abcd1234",
                                             password_confirm="Abcd1234", display_name="Bug"))
    ws = WordSet(owner_id=user.id, name="S", category="G", difficulty="beginner")
    db.add(ws)
    db.flush()
    multi = Item(word_set_id=ws.id, word="summarize", meaning="Tóm tắt, tổng kết")
    multi2 = Item(word_set_id=ws.id, word="leap", meaning="nhảy vọt; bước nhảy")
    single = Item(word_set_id=ws.id, word="cat", meaning="con mèo")
    db.add_all([multi, multi2, single])
    db.flush()
    session = StudySession(user_id=user.id, word_set_id=ws.id, mode="dkt_smart",
                           status="completed", started_at=T0)
    db.add(session)
    db.flush()
    return user, ws, session, multi, multi2, single


def _answer(db, user, session, item, at, correct, fmt="quiz", **kw):
    it = Interaction(user_id=user.id, item_id=item.id, session_id=session.id, is_correct=correct,
                     exercise_format=fmt, answered_at=at, **kw)
    db.add(it)
    db.flush()
    return it


def test_build_history_bo_qua_luot_bi_loai(db_session):
    user, _, session, multi, _, single = _world(db_session)
    _answer(db_session, user, session, multi, T0, False, excluded_reason="grading_bug_2026-10-26")
    _answer(db_session, user, session, single, T0 + timedelta(minutes=1), True)
    history, formats, _ = build_history(db_session, user.id)
    assert history == [("cat", 1)]


def test_fix_khoi_phuc_loai_tru_va_go_lich(db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, targets, **kw: {t: 0.7 for t in targets})
    user, _, session, multi, multi2, single = _world(db_session)

    # (a) lượt có request_hash, người học chọn đúng nghĩa chính -> khôi phục thành đúng
    cid = uuid.uuid4()
    req = AnswerRequest(item_id=multi.id, is_correct=True, answer="tóm tắt",
                        client_answer_id=cid, response_time_ms=900)
    a = _answer(db_session, user, session, multi, T0, False, client_answer_id=str(cid), response_time_ms=900,
                request_hash=hashlib.sha256(req.model_dump_json().encode()).hexdigest())
    # (b) không có hash -> loại trừ
    b = _answer(db_session, user, session, multi2, T0 + timedelta(minutes=1), False)
    # (c) từ một nghĩa vẫn chấm đúng lúc lỗi -> không đụng
    c = _answer(db_session, user, session, single, T0 + timedelta(minutes=2), False)
    # (d) bản sửa lên: lượt nhiều nghĩa đúng đầu tiên; (e) sai sau đó là sai THẬT
    _answer(db_session, user, session, multi2, T0 + timedelta(hours=5), True)
    e = _answer(db_session, user, session, multi, T0 + timedelta(hours=6), False)

    db_session.add(KnowledgeState(user_id=user.id, item_id=multi2.id, mastery=0.1, last_updated=T0))
    db_session.add(ReviewSchedule(user_id=user.id, item_id=multi2.id, next_review_at=T0,
                                  interval_days=1, half_life_days=1.0))
    db_session.flush()

    assert fixmod.find_fix_time(db_session, T0 - timedelta(hours=1)) == T0 + timedelta(hours=5)
    until = T0 + timedelta(hours=5)
    result = fixmod.fix(db_session, until=until, since=T0 - timedelta(hours=1))
    assert result.recovered_correct == [a.id] and result.excluded == [b.id]
    assert a.is_correct is True and a.excluded_reason is None
    assert b.excluded_reason == fixmod.REASON and b.is_correct is False   # bản ghi vẫn giữ
    assert c.excluded_reason is None and e.excluded_reason is None and e.is_correct is False

    ks = db_session.query(KnowledgeState).filter_by(user_id=user.id, item_id=multi2.id).one()
    assert ks.mastery == 0.7
    rs = db_session.query(ReviewSchedule).filter_by(user_id=user.id, item_id=multi2.id).one()
    assert rs.half_life_days == 2.0  # gỡ đúng một lần co ×0,5
    assert db_session.get(StudySession, session.id).correct_count == 2

    # Chạy lại: không đụng gì thêm.
    again = fixmod.fix(db_session, until=until, since=T0 - timedelta(hours=1))
    assert again.recovered_correct == [] and again.excluded == [] and again.schedules_fixed == 0
