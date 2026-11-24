"""UC-11 — kiểm tra trình độ đầu vào (placement test)."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.placement import PlacementAttempt, PlacementQuestion
from app.models.user_settings import UserSettings
from app.schemas.auth import RegisterRequest
from app.services import placement_service, roadmap_seed
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _bank(db_session):
    roadmap_seed.seed_placement_questions(db_session)
    return db_session.execute(select(PlacementQuestion)).scalars().all()


def _answers(questions, *, correct_levels: set[str]):
    """Trả lời đúng ở các mức trong `correct_levels`, sai ở mức còn lại."""
    out = []
    for q in questions:
        answer = q.correct_meaning if q.cefr_level in correct_levels else q.distractors[0]
        out.append({"question_id": q.id, "answer": answer})
    return out


def test_questions_cover_all_levels_without_answers(client, db_session):
    _bank(db_session)
    _, headers = _user(db_session, "pl.a@example.com")

    body = client.get("/api/v1/placement/questions", headers=headers).json()
    assert {q["cefr_level"] for q in body} == {"A1", "A2", "B1", "B2", "C1"}
    assert all(len(q["options"]) == 4 for q in body)
    assert all("correct_meaning" not in q for q in body)   # không lộ đáp án


def test_status_before_and_after(client, db_session):
    _bank(db_session)
    _, headers = _user(db_session, "pl.b@example.com")

    before = client.get("/api/v1/placement/status", headers=headers).json()
    assert before["has_placement"] is False and before["entry_cefr_level"] is None

    client.post("/api/v1/placement/skip", headers=headers)

    after = client.get("/api/v1/placement/status", headers=headers).json()
    assert after["has_placement"] is True and after["entry_cefr_level"] == "A1"


def test_skip_gives_a1(client, db_session):
    """Luồng thay thế 1a — "Tôi mới bắt đầu"."""
    user, headers = _user(db_session, "pl.c@example.com")

    body = client.post("/api/v1/placement/skip", headers=headers).json()
    assert body["estimated_level"] == "A1" and body["skipped"] is True
    assert body["answered_count"] == 0

    settings_row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    assert settings_row.entry_cefr_level == "A1"


def test_estimate_stops_at_first_failed_level(client, db_session):
    """Đúng A1+A2, sai B1 -> A2. Đoán trúng mức cao hơn không đẩy trình độ lên."""
    questions = _bank(db_session)
    user, headers = _user(db_session, "pl.d@example.com")

    body = client.post("/api/v1/placement/submit", headers=headers, json={
        "answers": _answers(questions, correct_levels={"A1", "A2", "C1"}),
    }).json()

    assert body["estimated_level"] == "A2"
    assert body["entry_cefr_level"] == "A2"
    assert placement_service.entry_level(db_session, user) == "A2"


def test_all_correct_gives_highest_level(client, db_session):
    questions = _bank(db_session)
    _, headers = _user(db_session, "pl.e@example.com")

    body = client.post("/api/v1/placement/submit", headers=headers, json={
        "answers": _answers(questions, correct_levels={"A1", "A2", "B1", "B2", "C1"}),
    }).json()
    assert body["estimated_level"] == "C1"
    assert body["correct_count"] == len(questions)


def test_all_wrong_falls_back_to_a1(client, db_session):
    """BR-10 — thiếu dữ liệu / không đạt mức nào -> mức mặc định."""
    questions = _bank(db_session)
    _, headers = _user(db_session, "pl.f@example.com")

    body = client.post("/api/v1/placement/submit", headers=headers, json={
        "answers": _answers(questions, correct_levels=set()),
    }).json()
    assert body["estimated_level"] == "A1" and body["correct_count"] == 0


def test_partial_submit_is_scored(client, db_session):
    """E1 — thoát giữa chừng: chỉ nộp phần đã làm, vẫn chấm được."""
    questions = _bank(db_session)
    a1 = [q for q in questions if q.cefr_level == "A1"]
    _, headers = _user(db_session, "pl.g@example.com")

    body = client.post("/api/v1/placement/submit", headers=headers, json={
        "answers": _answers(a1, correct_levels={"A1"}),
    }).json()

    assert body["answered_count"] == len(a1)
    assert body["estimated_level"] == "A1"   # không có dữ liệu mức cao hơn -> dừng
    assert [b["cefr_level"] for b in body["per_level"]] == ["A1"]


def test_empty_submit_defaults_to_a1(client, db_session):
    _bank(db_session)
    _, headers = _user(db_session, "pl.h@example.com")
    body = client.post("/api/v1/placement/submit", headers=headers, json={"answers": []}).json()
    assert body["estimated_level"] == "A1" and body["answered_count"] == 0


def test_attempt_is_recorded(client, db_session):
    questions = _bank(db_session)
    user, headers = _user(db_session, "pl.i@example.com")
    client.post("/api/v1/placement/submit", headers=headers, json={
        "answers": _answers(questions, correct_levels={"A1"}),
    })

    attempt = db_session.execute(
        select(PlacementAttempt).where(PlacementAttempt.user_id == user.id)
    ).scalars().one()
    assert attempt.status == "completed" and attempt.estimated_level == "A1"
    assert attempt.per_level["A1"]["correct"] == 4


def test_pass_ratio_is_configurable(client, db_session):
    """Ngưỡng đạt mỗi mức lấy từ cấu hình hệ thống (UC-81): cùng một bài làm,
    hạ ngưỡng thì trình độ ước lượng tăng."""
    questions = _bank(db_session)
    from app.services import config_service

    a1 = [q for q in questions if q.cefr_level == "A1"]
    a2 = [q for q in questions if q.cefr_level == "A2"]
    answers = (
        [{"question_id": q.id, "answer": q.correct_meaning} for q in a1]          # A1: 4/4
        + [{"question_id": q.id,
            "answer": q.correct_meaning if i < 2 else q.distractors[0]}
           for i, q in enumerate(a2)]                                             # A2: 2/4 = 0.5
    )

    # ngưỡng mặc định 0.6 -> A2 trượt
    _, headers = _user(db_session, "pl.j@example.com")
    assert client.post("/api/v1/placement/submit", headers=headers,
                       json={"answers": answers}).json()["estimated_level"] == "A1"

    # hạ ngưỡng xuống 0.5 -> A2 đạt
    config_service.set_values(db_session, {"placement_pass_ratio": 0.5})
    _, headers2 = _user(db_session, "pl.k@example.com")
    assert client.post("/api/v1/placement/submit", headers=headers2,
                       json={"answers": answers}).json()["estimated_level"] == "A2"


def test_no_questions_returns_404(client, db_session):
    _, headers = _user(db_session, "pl.l@example.com")
    assert client.get("/api/v1/placement/questions", headers=headers).status_code == 404


def test_placement_requires_auth(client):
    assert client.get("/api/v1/placement/status").status_code == 401
