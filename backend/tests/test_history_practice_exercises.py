"""UC-45 lịch sử học tập · UC-35 luyện thường · UC-28 điền khuyết & ghép cặp."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.review_schedule import ReviewSchedule
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service, dkt_client
from app.services.auth_service import register_user


def _setup(db_session, email: str, *, n_items: int = 4, with_examples: bool = False):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set0", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [
        Item(
            word_set_id=ws.id, word=f"word{i}", meaning=f"nghia{i}",
            example=(f"I use word{i} every day." if with_examples else None),
        )
        for i in range(n_items)
    ]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _play(client, headers, *, word_set_id, mode, items, practice_only=False):
    """Mở phiên, trả lời hết item, kết thúc. Trả về tổng kết."""
    body = {"word_set_id": word_set_id, "mode": mode, "practice_only": practice_only}
    sid = client.post("/api/v1/sessions", json=body, headers=headers).json()["id"]
    for it in items:
        response = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                    json={"item_id": it.id, "is_correct": True, "response_time_ms": 500,
                          "answer": it.meaning if mode in {"quiz", "matching"} else it.word})
        assert response.status_code == 204, response.text
    return sid, client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()


# ---------------------------------------------------------------- UC-45

def test_history_lists_finished_sessions_newest_first(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers, ws, items = _setup(db_session, "hist.a@example.com")

    _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:2])
    _play(client, headers, word_set_id=ws.id, mode="quiz", items=items[:3])

    body = client.get("/api/v1/sessions/history", headers=headers).json()
    assert body["total"] == 2
    assert [row["mode"] for row in body["items"]] == ["quiz", "flashcard"]  # mới nhất trước

    newest = body["items"][0]
    assert newest["item_count"] == 3 and newest["correct_count"] == 3
    assert newest["accuracy"] == 1.0
    assert newest["word_set_name"] == "Set0"
    assert newest["duration_seconds"] is not None

    # tổng hợp tính trên toàn bộ lịch sử
    assert body["total_sessions"] == 2
    assert body["total_items_answered"] == 5
    # BR-XP-01: 5 LƯỢT đúng nhưng chỉ 3 TỪ khác nhau (phiên hai học lại items[0:2]),
    # nên XP tính trên 3 từ. Đây là chỗ chặn cày XP bằng cách bấm lại từ cũ.
    assert body["total_xp"] == 3 * config_service.get_int("xp_per_correct")


def test_history_hides_in_progress_session(client, db_session):
    _, headers, ws, _ = _setup(db_session, "hist.b@example.com")
    client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                headers=headers)

    body = client.get("/api/v1/sessions/history", headers=headers).json()
    assert body["total"] == 0 and body["items"] == []


def test_history_filter_and_pagination(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers, ws, items = _setup(db_session, "hist.c@example.com")
    for _ in range(3):
        _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:1])
    _play(client, headers, word_set_id=ws.id, mode="quiz", items=items[:1])

    only_quiz = client.get("/api/v1/sessions/history?mode=quiz", headers=headers).json()
    assert only_quiz["total"] == 1 and only_quiz["total_items_answered"] == 1

    page2 = client.get("/api/v1/sessions/history?page=2&page_size=3", headers=headers).json()
    assert page2["total"] == 4 and len(page2["items"]) == 1


def test_history_isolated_per_user(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers, ws, items = _setup(db_session, "hist.d@example.com")
    _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:1])

    _, other, _, _ = _setup(db_session, "hist.e@example.com")
    assert client.get("/api/v1/sessions/history", headers=other).json()["total"] == 0


# ------------------------------------------------------ Phiên đang dở

def test_resume_returns_latest_unfinished_session(client, db_session):
    _, headers, ws, items = _setup(db_session, "res.a@example.com")
    assert client.get("/api/v1/sessions/resume", headers=headers).json() is None

    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                json={"item_id": items[0].id, "is_correct": True})

    body = client.get("/api/v1/sessions/resume", headers=headers).json()
    assert body["session_id"] == sid
    assert body["word_set_name"] == "Set0"
    assert body["answered_count"] == 1

    client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert client.get("/api/v1/sessions/resume", headers=headers).json() is None


# ---------------------------------------------------------------- UC-35

def test_practice_only_does_not_touch_review_schedule(client, db_session, monkeypatch):
    """Luyện thường: vẫn ghi Interaction & đổi mastery, nhưng KHÔNG xê dịch lịch ôn."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    user, headers, ws, items = _setup(db_session, "prac.a@example.com")

    _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:1],
          practice_only=True)

    schedules = db_session.execute(
        select(ReviewSchedule).where(ReviewSchedule.user_id == user.id)
    ).scalars().all()
    assert schedules == []          # không tạo lịch mới

    # nhưng lượt trả lời vẫn được ghi -> có mặt trong lịch sử
    history = client.get("/api/v1/sessions/history", headers=headers).json()
    assert history["items"][0]["item_count"] == 1


def test_normal_session_still_schedules_review(client, db_session, monkeypatch):
    """Đối chứng: cùng thao tác nhưng không bật luyện thường thì PHẢI có lịch ôn."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    user, headers, ws, items = _setup(db_session, "prac.b@example.com")

    _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:1])

    schedules = db_session.execute(
        select(ReviewSchedule).where(ReviewSchedule.user_id == user.id)
    ).scalars().all()
    assert len(schedules) == 1


def test_practice_only_keeps_existing_schedule_untouched(client, db_session, monkeypatch):
    """Đã có lịch từ trước: luyện thường không được đẩy next_review_at đi."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    user, headers, ws, items = _setup(db_session, "prac.c@example.com")

    _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:1])
    before = db_session.execute(
        select(ReviewSchedule).where(ReviewSchedule.user_id == user.id)
    ).scalar_one()
    original_at, original_interval = before.next_review_at, before.interval_days

    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.1 for x in t})
    _play(client, headers, word_set_id=ws.id, mode="flashcard", items=items[:1],
          practice_only=True)

    db_session.refresh(before)
    assert before.next_review_at == original_at
    assert before.interval_days == original_interval


def test_practice_flag_visible_on_session(client, db_session):
    _, headers, ws, _ = _setup(db_session, "prac.d@example.com")
    created = client.post("/api/v1/sessions", headers=headers,
                          json={"word_set_id": ws.id, "mode": "flashcard",
                                "practice_only": True}).json()
    assert created["practice_only"] is True


# ---------------------------------------------------------------- UC-28

def test_cloze_blanks_the_target_word(client, db_session):
    _, headers, ws, _ = _setup(db_session, "cloze.a@example.com", with_examples=True)

    rows = client.get(f"/api/v1/word-sets/{ws.id}/cloze?limit=3", headers=headers).json()
    assert len(rows) == 3
    for row in rows:
        assert "____" in row["sentence"]
        assert row["answer"] not in row["sentence"]     # từ cần điền đã bị che
        assert row["hint"].startswith("nghia")


def test_cloze_rejects_word_set_without_usable_examples(client, db_session):
    """E1 — không có ví dụ nào chứa chính từ cần học."""
    _, headers, ws, _ = _setup(db_session, "cloze.b@example.com", with_examples=False)

    r = client.get(f"/api/v1/word-sets/{ws.id}/cloze", headers=headers)
    assert r.status_code == 400
    assert "ví dụ" in r.json()["detail"]


def test_cloze_skips_items_whose_example_lacks_the_word(client, db_session):
    _, headers, ws, items = _setup(db_session, "cloze.c@example.com", with_examples=True)
    items[0].example = "Câu này không chứa từ cần học."
    db_session.commit()

    rows = client.get(f"/api/v1/word-sets/{ws.id}/cloze", headers=headers).json()
    assert items[0].word not in {row["answer"] for row in rows}
    assert len(rows) == 3


def test_matching_returns_pairs_with_shuffled_meanings(client, db_session):
    _, headers, ws, _ = _setup(db_session, "match.a@example.com", n_items=6)

    body = client.get(f"/api/v1/word-sets/{ws.id}/matching", headers=headers).json()
    assert len(body["pairs"]) == config_service.get_int("matching_round_size")

    meanings = [p["meaning"] for p in body["pairs"]]
    assert sorted(body["shuffled_meanings"]) == sorted(meanings)   # cùng tập
    assert body["shuffled_meanings"] != meanings                   # nhưng khác thứ tự


def test_matching_round_size_from_config(client, db_session):
    _, headers, ws, _ = _setup(db_session, "match.b@example.com", n_items=6)
    config_service.set_values(db_session, {"matching_round_size": 3})

    body = client.get(f"/api/v1/word-sets/{ws.id}/matching", headers=headers).json()
    assert len(body["pairs"]) == 3


def test_matching_needs_at_least_two_items(client, db_session):
    _, headers, ws, _ = _setup(db_session, "match.c@example.com", n_items=1)
    r = client.get(f"/api/v1/word-sets/{ws.id}/matching", headers=headers)
    assert r.status_code == 400


def test_cloze_and_matching_are_valid_session_modes(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers, ws, items = _setup(db_session, "mode.a@example.com", with_examples=True)

    for mode in ("cloze", "matching"):
        _, summary = _play(client, headers, word_set_id=ws.id, mode=mode, items=items[:2])
        assert summary["total_answered"] == 2


def test_exercises_require_owned_word_set(client, db_session):
    _, _, ws, _ = _setup(db_session, "own.a@example.com", with_examples=True)
    _, other, _, _ = _setup(db_session, "own.b@example.com")

    assert client.get(f"/api/v1/word-sets/{ws.id}/cloze", headers=other).status_code == 404
    assert client.get(f"/api/v1/word-sets/{ws.id}/matching", headers=other).status_code == 404


# -------------------------------------------------- Tự chọn trình độ đầu vào

def test_learner_can_override_entry_level(client, db_session):
    """Mức do bài kiểm tra ước lượng, nhưng người học chỉnh thẳng được (UC-10/11)."""
    user, headers, _, _ = _setup(db_session, "entry.a@example.com")

    body = client.put("/api/v1/users/me/goals", headers=headers,
                      json={"entry_cefr_level": "B2"}).json()
    assert body["entry_cefr_level"] == "B2"

    row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    db_session.refresh(row)
    assert row.entry_cefr_level == "B2"

    # lộ trình (UC-84) xuất phát từ mức mới
    assert client.get("/api/v1/me/roadmap", headers=headers).json()["entry_level"] == "B2"


def test_entry_level_rejects_invalid_value(client, db_session):
    _, headers, _, _ = _setup(db_session, "entry.b@example.com")
    r = client.put("/api/v1/users/me/goals", headers=headers,
                   json={"entry_cefr_level": "Z9"})
    assert r.status_code == 422


def test_new_endpoints_require_auth(client):
    assert client.get("/api/v1/sessions/history").status_code == 401
    assert client.get("/api/v1/sessions/resume").status_code == 401
    assert client.get("/api/v1/word-sets/1/cloze").status_code == 401
    assert client.get("/api/v1/word-sets/1/matching").status_code == 401
