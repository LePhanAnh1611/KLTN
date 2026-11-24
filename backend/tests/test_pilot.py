"""Pilot kiểm chứng DKT: thăm dò ngẫu nhiên, chấm khách quan thẻ lật, bài kiểm tra
cuối, báo cáo theo dõi."""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.interaction import Interaction
from app.models.item import Item
from app.models.review_schedule import ReviewSchedule
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service, dkt_client, pilot_service, recommend_service
from app.services.auth_service import register_user
from app.services.validation_service import stratified_sample


def _setup(db_session, email, n_items=12, role="learner"):
    user = register_user(db_session, RegisterRequest(
        email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:5]))
    if role != "learner":
        user.role = role
        db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="S", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"word{i}", meaning=f"nghia{i}") for i in range(n_items)]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _set_config(**values):
    config_service._cache = {k: str(v).lower() if isinstance(v, bool) else str(v)
                             for k, v in values.items()}


def _fixed_dkt(monkeypatch, value: float):
    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda history, targets, **kw: {t: value for t in targets})


# ---- Thăm dò ngẫu nhiên -------------------------------------------------------

class _It:
    def __init__(self, i):
        self.id = i


def test_mix_in_exploration_replaces_part_with_random_items():
    chosen = [(_It(i), 0.7) for i in range(20)]
    scored = chosen + [(_It(100 + i), 0.1) for i in range(10)]
    picks = recommend_service.mix_in_exploration(chosen, scored, 0.15, random.Random(1))

    assert len(picks) == 20
    explore = [it.id for it, _, r in picks if r == "explore"]
    assert len(explore) == 3
    assert all(i >= 100 for i in explore)           # lấy ngoài danh sách vừa sức
    assert len({it.id for it, _, _ in picks}) == 20  # không trùng


def test_mix_in_exploration_off_or_no_pool():
    chosen = [(_It(i), 0.7) for i in range(5)]
    assert {r for _, _, r in recommend_service.mix_in_exploration(chosen, chosen, 0.0)} == {"band"}
    # không còn từ nào ngoài danh sách -> không thăm dò được
    assert {r for _, _, r in recommend_service.mix_in_exploration(chosen, chosen, 0.5)} == {"band"}


def test_recommend_marks_selection(client, db_session):
    _, headers, ws, _ = _setup(db_session, "plt.rec@example.com", n_items=12)
    rows = client.get(f"/api/v1/word-sets/{ws.id}/recommend?limit=10", headers=headers).json()
    assert len(rows) == 10
    assert sum(r["selection"] == "explore" for r in rows) == 2   # round(10 * 0.15)

    _set_config(explore_rate=0)
    rows = client.get(f"/api/v1/word-sets/{ws.id}/recommend?limit=10", headers=headers).json()
    assert {r["selection"] for r in rows} == {"band"}


# ---- Chấm khách quan thẻ lật --------------------------------------------------

def test_quiz_questions_for_items(client, db_session):
    _, headers, _, items = _setup(db_session, "plt.q@example.com", n_items=6)
    _, _, _, other = _setup(db_session, "plt.q2@example.com", n_items=6)
    ids = [items[2].id, items[0].id, other[0].id]

    rows = client.post("/api/v1/sessions/quiz-questions", json={"item_ids": ids},
                       headers=headers).json()
    assert [r["item_id"] for r in rows] == [items[2].id, items[0].id]  # bỏ từ người khác
    for r in rows:
        assert len(set(r["options"])) == 4
        assert r["options"][r["correct_index"]] == f"nghia{r['word'][4:]}"


def test_quiz_questions_alternate_with_flashcard(client, db_session):
    """Lần trước trắc nghiệm -> lần này thẻ lật (không có câu hỏi) và ngược lại."""
    user, headers, ws, items = _setup(db_session, "plt.alt@example.com", n_items=6)
    now = datetime.now(timezone.utc)

    def answered(item, fmt, minutes_ago, excluded=None):
        db_session.add(Interaction(user_id=user.id, item_id=item.id, is_correct=True,
                                   exercise_format=fmt, excluded_reason=excluded,
                                   answered_at=now - timedelta(minutes=minutes_ago)))

    answered(items[0], "quiz", 5)                       # gần nhất: trắc nghiệm
    answered(items[1], "quiz", 10)
    answered(items[1], "srs_review", 5)                 # gần nhất: thẻ lật
    answered(items[2], "dkt_smart", 10)
    answered(items[2], "quiz", 5, excluded="grading_bug_2026-10-26")  # bị loại -> bỏ qua
    db_session.commit()

    ids = [it.id for it in items[:4]]                   # items[3]: chưa học lần nào
    rows = client.post("/api/v1/sessions/quiz-questions", json={"item_ids": ids},
                       headers=headers).json()
    assert [r["item_id"] for r in rows] == [items[1].id, items[2].id, items[3].id]

    _set_config(alternate_card_quiz=False)              # tắt -> như cũ, luôn trắc nghiệm
    rows = client.post("/api/v1/sessions/quiz-questions", json={"item_ids": ids},
                       headers=headers).json()
    assert [r["item_id"] for r in rows] == ids


def test_dkt_smart_answer_graded_objectively(client, db_session):
    user, headers, ws, items = _setup(db_session, "plt.g@example.com")
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "dkt_smart"},
                      headers=headers).json()["id"]

    # Client nói "đúng" nhưng chọn sai nghĩa -> server chấm SAI
    r = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
        "item_id": items[0].id, "is_correct": True, "answer": "nghia5",
        "exercise_format": "quiz", "selection_reason": "explore"})
    assert r.status_code == 204
    r = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
        "item_id": items[1].id, "answer": "nghia1", "exercise_format": "quiz",
        "selection_reason": "band"})
    assert r.status_code == 204

    rows = db_session.execute(select(Interaction).where(Interaction.session_id == sid)
                              .order_by(Interaction.id)).scalars().all()
    assert [(i.is_correct, i.exercise_format, i.selection_reason) for i in rows] == [
        (False, "quiz", "explore"), (True, "quiz", "band")]


def test_dkt_smart_flashcard_still_works(client, db_session):
    """Không gửi câu hỏi khách quan -> giữ hành vi cũ (tự đánh giá)."""
    _, headers, ws, items = _setup(db_session, "plt.f@example.com")
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "dkt_smart"},
                      headers=headers).json()["id"]
    assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
        "item_id": items[0].id, "is_correct": True}).status_code == 204
    i = db_session.execute(select(Interaction).where(Interaction.session_id == sid)).scalar_one()
    assert (i.is_correct, i.exercise_format, i.selection_reason) == (True, "dkt_smart", None)


def test_review_answer_marked_review(client, db_session):
    _, headers, _, items = _setup(db_session, "plt.r@example.com")
    sid = client.post("/api/v1/sessions", json={"mode": "srs_review"}, headers=headers).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
        "item_id": items[0].id, "answer": "nghia0", "exercise_format": "quiz"})
    i = db_session.execute(select(Interaction).where(Interaction.session_id == sid)).scalar_one()
    assert (i.is_correct, i.exercise_format, i.selection_reason) == (True, "quiz", "review")


# ---- Bài kiểm tra cuối --------------------------------------------------------

def _study(client, headers, ws, items):
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "quiz"},
                      headers=headers).json()["id"]
    for it in items:
        client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                    json={"item_id": it.id, "answer": it.meaning})
    client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)


def test_validation_flow(client, db_session, monkeypatch):
    user, headers, ws, items = _setup(db_session, "plt.v@example.com", n_items=14)

    assert client.post("/api/v1/validation/start", headers=headers).status_code == 403
    _set_config(validation_open=True, validation_size=10)
    assert client.post("/api/v1/validation/start", headers=headers).status_code == 400  # chưa học

    _study(client, headers, ws, items[:12])
    status = client.get("/api/v1/validation/status", headers=headers).json()
    assert status["open"] and not status["done"] and status["eligible_items"] == 12

    _fixed_dkt(monkeypatch, 0.42)
    body = client.post("/api/v1/validation/start", headers=headers).json()
    sid, questions = body["session_id"], body["questions"]
    assert len(questions) == 10
    assert "answer" not in questions[0]                     # không lộ đáp án
    asked = {q["item_id"] for q in questions}
    assert asked <= {it.id for it in items[:12]}            # chỉ từ đã học

    # từ không có trong đề -> 404
    assert client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                       json={"item_id": items[13].id, "answer": "x"}).status_code == 404

    by_id = {it.id: it for it in items}
    first, second = questions[0]["item_id"], questions[1]["item_id"]
    before = db_session.execute(select(ReviewSchedule.next_review_at, ReviewSchedule.half_life_days)
                                .where(ReviewSchedule.item_id == second)).one()
    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                json={"item_id": first, "answer": f" {by_id[first].word.upper()} "})
    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                json={"item_id": second, "answer": "sai"})

    # vào lại giữa chừng -> cùng phiên, còn 8 câu
    again = client.post("/api/v1/validation/start", headers=headers).json()
    assert again["session_id"] == sid and len(again["questions"]) == 8

    rows = db_session.execute(select(Interaction).where(Interaction.session_id == sid)
                              .order_by(Interaction.id)).scalars().all()
    assert [(i.is_correct, i.exercise_format, i.selection_reason) for i in rows] == [
        (True, "typing", "validation"), (False, "typing", "validation")]
    assert rows[0].predicted_mastery == 0.42 and rows[0].prediction_source == "model"
    # practice_only -> không tạo/không đổi lịch ôn từ bài kiểm tra
    after = db_session.execute(select(ReviewSchedule.next_review_at, ReviewSchedule.half_life_days)
                               .where(ReviewSchedule.item_id == second)).one()
    assert after == before

    # bắt đầu phiên ôn khác KHÔNG được làm mất bài kiểm tra đang dở
    client.post("/api/v1/sessions", json={"mode": "srs_review"}, headers=headers)
    assert client.post("/api/v1/validation/start", headers=headers).json()["session_id"] == sid
    assert client.get("/api/v1/sessions/resume", headers=headers).json()["mode"] != "validation"

    client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert client.get("/api/v1/validation/status", headers=headers).json()["done"] is True
    assert client.post("/api/v1/validation/start", headers=headers).status_code == 409


def test_stratified_sample_spreads_bins():
    scored = [(_It(i), (i % 50) / 50) for i in range(200)]
    picked = stratified_sample(scored, 30, random.Random(3))
    assert len(picked) == 30
    counts = [0] * 5
    for _, p in picked:
        counts[min(int(p * 5), 4)] += 1
    assert counts == [6, 6, 6, 6, 6]

    # một khoảng thiếu -> bù từ khoảng khác, vẫn đủ số câu
    skewed = [(_It(i), 0.95) for i in range(40)] + [(_It(100 + i), 0.1) for i in range(3)]
    assert len(stratified_sample(skewed, 30, random.Random(3))) == 30


# ---- Báo cáo theo dõi ---------------------------------------------------------

def _answers(db_session, user, item, when, n=1, p=0.75, correct=True):
    for k in range(n):
        db_session.add(Interaction(
            user_id=user.id, item_id=item.id, is_correct=correct,
            predicted_mastery=p, prediction_source="model",
            answered_at=when + timedelta(seconds=k)))
    db_session.commit()


def test_pilot_report_counts_and_email(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "pilot_start_date", None)
    a, _, _, items_a = _setup(db_session, "plt.ra@example.com")
    b, _, _, _ = _setup(db_session, "plt.rb@example.com")
    _, admin_headers, _, items_admin = _setup(db_session, "plt.adm@example.com", role="admin")

    now = datetime.now(timezone.utc)
    # a học 3 ngày khác nhau, ôn lại word0 sau 2 ngày
    _answers(db_session, a, items_a[0], now - timedelta(days=4), n=2, p=0.15, correct=False)
    _answers(db_session, a, items_a[0], now - timedelta(days=2), n=1, p=0.55)
    _answers(db_session, a, items_a[1], now - timedelta(days=2), n=3, p=0.95)
    # admin trả lời -> KHÔNG được tính
    db_session.add(Interaction(user_id=_admin_id(db_session),
                               item_id=items_admin[0].id, is_correct=True,
                               answered_at=now, prediction_source="model", predicted_mastery=0.5))
    db_session.commit()

    report = client.get("/api/v1/admin/pilot", headers=admin_headers).json()
    people = {p["email"]: p for p in report["people"]}
    assert set(people) >= {"plt.ra@example.com", "plt.rb@example.com"}
    assert "plt.adm@example.com" not in people
    assert people["plt.ra@example.com"]["answers_total"] == 6
    assert people["plt.ra@example.com"]["active_days"] == 2
    assert people["plt.ra@example.com"]["needs_nudge"] is True       # 2 ngày chưa vào
    assert report["answers_total"] >= 6 and report["model_share"] == 1.0
    gap = next(c for c in report["criteria"] if c["key"] == "gap_answers")
    assert gap["current"] >= 1                                       # word0 ôn lại sau 2 ngày
    low_bin = report["bins"][1]
    assert low_bin["count"] >= 2 and low_bin["accuracy"] == 0.0
    assert report["ready"] is False

    from app.schemas.pilot import PilotReport
    subject, body = pilot_service.render_email(PilotReport.model_validate(report))
    assert "đạt 0/4" in subject or "đạt" in subject
    assert "plt.ra" in body and "CẦN NHẮC" in body


def _admin_id(db_session):
    from app.models.user import User
    return db_session.execute(select(User.id).where(User.email == "plt.adm@example.com")).scalar_one()


def test_pilot_report_requires_admin(client, db_session):
    _, headers, _, _ = _setup(db_session, "plt.nonadm@example.com")
    assert client.get("/api/v1/admin/pilot", headers=headers).status_code == 403


def test_pilot_email_ready_subject():
    from app.schemas.pilot import PilotCriterion, PilotReport
    crit = [PilotCriterion(key="k", label="L", why="w", current=5, target=5, met=True)]
    report = PilotReport(
        generated_at=datetime.now(timezone.utc), pilot_start=None, pilot_day=None,
        registered=1, participants=1, active_today=1, answers_today=3, answers_total=3,
        model_share=1.0, explore_answers=0, validation_done=0, criteria=crit, ready=True,
        bins=[], people=[])
    subject, body = pilot_service.render_email(report)
    assert "ĐÃ ĐỦ DỮ LIỆU" in subject and "làm phân tích" in body


def test_pilot_report_written_to_files(tmp_path):
    """Kênh báo cáo qua file: latest.txt/.json + bản theo ngày, ghi đè mỗi lần."""
    import json
    from app.schemas.pilot import PilotCriterion, PilotReport
    crit = [PilotCriterion(key="k", label="L", why="w", current=1, target=5, met=False)]
    report = PilotReport(
        generated_at=datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc), pilot_start=None,
        pilot_day=1, registered=3, participants=2, active_today=2, answers_today=40,
        answers_total=40, model_share=0.97, explore_answers=6, validation_done=0,
        criteria=crit, ready=False, bins=[], people=[])
    pilot_service.write_report_files(report, tmp_path)
    assert "Ngày 1" in (tmp_path / "latest.txt").read_text(encoding="utf-8")
    assert (tmp_path / "2026-10-16.txt").exists()          # 21h giờ VN = 14h UTC cùng ngày
    data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert data["active_today"] == 2 and data["ready"] is False
