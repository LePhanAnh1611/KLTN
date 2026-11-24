from app.core.security import create_access_token
from app.models.interaction import Interaction
from app.models.item import Item
from app.models.session import StudySession
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _setup(db_session, email: str, n_items: int = 4):
    user = register_user(
        db_session,
        RegisterRequest(
            email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"
        ),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    word_set = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(word_set)
    db_session.flush()
    items = [
        Item(word_set_id=word_set.id, word=f"word{i}", meaning=f"nghia{i}")
        for i in range(n_items)
    ]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, word_set, items


def _start(client, headers, word_set_id, mode="flashcard") -> int:
    resp = client.post(
        "/api/v1/sessions", json={"word_set_id": word_set_id, "mode": mode}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------- UC-25/26: ghi INTERACTION (BR-05) ----------


def test_record_answer_persists_full_interaction(client, db_session):
    user, headers, ws, items = _setup(db_session, "sess.a@example.com")
    sid = _start(client, headers, ws.id, mode="flashcard")

    resp = client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items[0].id, "is_correct": True, "response_time_ms": 1500},
        headers=headers,
    )
    assert resp.status_code == 204

    interaction = db_session.query(Interaction).filter_by(session_id=sid).one()
    assert interaction.user_id == user.id
    assert interaction.item_id == items[0].id
    assert interaction.is_correct is True
    assert interaction.response_time_ms == 1500
    assert interaction.exercise_format == "flashcard"  # mặc định theo mode phiên
    assert interaction.answered_at is not None


def test_answer_item_not_in_set_404(client, db_session):
    _, headers, ws, _ = _setup(db_session, "sess.b@example.com")
    _, _, other_ws, other_items = _setup(db_session, "sess.b2@example.com")
    sid = _start(client, headers, ws.id)

    resp = client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": other_items[0].id, "is_correct": True},
        headers=headers,
    )
    assert resp.status_code == 404


def test_answer_on_foreign_session_404(client, db_session):
    _, headers_a, ws_a, items_a = _setup(db_session, "sess.owner@example.com")
    _, headers_b, _, _ = _setup(db_session, "sess.other@example.com")
    sid = _start(client, headers_a, ws_a.id)

    resp = client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items_a[0].id, "is_correct": True},
        headers=headers_b,
    )
    assert resp.status_code == 404


# ---------- UC-26: sinh quiz ----------


def test_quiz_generation(client, db_session):
    _, headers, ws, items = _setup(db_session, "quiz.a@example.com", n_items=4)
    resp = client.get(f"/api/v1/word-sets/{ws.id}/quiz", headers=headers)
    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) == 4
    for q in questions:
        assert len(q["options"]) == 4
        # đáp án đúng nằm đúng vị trí correct_index
        item = next(i for i in items if i.id == q["item_id"])
        assert q["options"][q["correct_index"]] == item.meaning


def test_quiz_requires_min_items(client, db_session):
    _, headers, ws, _ = _setup(db_session, "quiz.b@example.com", n_items=3)
    resp = client.get(f"/api/v1/word-sets/{ws.id}/quiz", headers=headers)
    assert resp.status_code == 400


# ---------- UC-30: tổng kết phiên ----------


def test_complete_session_summary(client, db_session):
    _, headers, ws, items = _setup(db_session, "sum.a@example.com")
    sid = _start(client, headers, ws.id)

    client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items[0].id, "is_correct": True},
        headers=headers,
    )
    client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items[1].id, "is_correct": False},
        headers=headers,
    )
    client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items[2].id, "is_correct": True},
        headers=headers,
    )

    resp = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_answered"] == 3
    assert summary["correct_count"] == 2
    assert summary["wrong_count"] == 1
    assert abs(summary["accuracy"] - 2 / 3) < 1e-6
    assert [w["item_id"] for w in summary["wrong_items"]] == [items[1].id]

    session = db_session.get(StudySession, sid)
    assert session.status == "completed"
    assert session.item_count == 3
    assert session.correct_count == 2
    assert session.ended_at is not None


def test_complete_empty_session(client, db_session):
    _, headers, ws, _ = _setup(db_session, "sum.b@example.com")
    sid = _start(client, headers, ws.id)
    resp = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_answered"] == 0
    assert resp.json()["accuracy"] == 0.0


def test_complete_twice_returns_saved_summary(client, db_session):
    _, headers, ws, _ = _setup(db_session, "sum.c@example.com")
    sid = _start(client, headers, ws.id)
    first = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    resp = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == first.json()


# ---------- UC-31: tạm dừng / tiếp tục / thoát ----------


def test_active_session_returns_answered_items(client, db_session):
    _, headers, ws, items = _setup(db_session, "life.a@example.com")
    sid = _start(client, headers, ws.id)
    client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items[0].id, "is_correct": True},
        headers=headers,
    )

    resp = client.get(f"/api/v1/sessions/active?word_set_id={ws.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["session"]["id"] == sid
    assert body["answered_item_ids"] == [items[0].id]


def test_active_session_none_when_no_session(client, db_session):
    _, headers, ws, _ = _setup(db_session, "life.b@example.com")
    resp = client.get(f"/api/v1/sessions/active?word_set_id={ws.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["session"] is None


def test_active_session_ignores_session_without_answers(client, db_session):
    """Mở màn học rồi thoát ngay (0 câu) -> lần sau KHÔNG hỏi "còn phiên học dở"."""
    _, headers, ws, _ = _setup(db_session, "life.empty@example.com")
    _start(client, headers, ws.id)

    resp = client.get(f"/api/v1/sessions/active?word_set_id={ws.id}", headers=headers)
    assert resp.json()["session"] is None
    assert client.get("/api/v1/sessions/resume", headers=headers).json() is None


def test_starting_new_session_abandons_old(client, db_session):
    _, headers, ws, _ = _setup(db_session, "life.c@example.com")
    old_sid = _start(client, headers, ws.id)
    new_sid = _start(client, headers, ws.id)
    assert new_sid != old_sid

    old = db_session.get(StudySession, old_sid)
    assert old.status == "abandoned"


def test_abandon_session(client, db_session):
    _, headers, ws, _ = _setup(db_session, "life.d@example.com")
    sid = _start(client, headers, ws.id)
    resp = client.post(f"/api/v1/sessions/{sid}/abandon", headers=headers)
    assert resp.status_code == 204
    assert db_session.get(StudySession, sid).status == "abandoned"


# ---------- Auth ----------


def test_sessions_require_auth(client):
    assert client.post("/api/v1/sessions", json={"word_set_id": 1, "mode": "quiz"}).status_code == 401


# ---------- Chấm đáp án chọn nghĩa theo nghĩa chính (answer_label) ----------


def test_quiz_answer_graded_against_displayed_main_meaning(client, db_session):
    """Phương án chỉ hiện nghĩa chính ("tóm tắt"), không phải nghĩa đầy đủ.

    Lỗi cũ: server so với `item.meaning` nguyên văn nên chọn đúng vẫn bị ghi sai
    — phiên 30 câu chỉ sai 1 mà báo 53% đúng.
    """
    user, headers, ws, items = _setup(db_session, "sess.label@example.com")
    items[0].meaning = "Tóm tắt, tổng kết (bài viết)"
    db_session.commit()
    sid = _start(client, headers, ws.id, mode="dkt_smart")

    for answer, expected in [("tóm tắt", True), ("Tóm tắt, tổng kết (bài viết)", True), ("tổng kết", False)]:
        resp = client.post(
            f"/api/v1/sessions/{sid}/answer",
            json={"item_id": items[0].id, "answer": answer, "exercise_format": "quiz"},
            headers=headers,
        )
        assert resp.status_code == 204, resp.text
    graded = [i.is_correct for i in db_session.query(Interaction).filter_by(session_id=sid).order_by(Interaction.id)]
    assert graded == [True, True, False]


def test_matching_answer_graded_against_displayed_main_meaning(client, db_session):
    user, headers, ws, items = _setup(db_session, "sess.match@example.com")
    items[0].meaning = "Nhảy vọt; bước nhảy"
    db_session.commit()
    sid = _start(client, headers, ws.id, mode="matching")
    resp = client.post(
        f"/api/v1/sessions/{sid}/answer",
        json={"item_id": items[0].id, "answer": "nhảy vọt"},
        headers=headers,
    )
    assert resp.status_code == 204, resp.text
    assert db_session.query(Interaction).filter_by(session_id=sid).one().is_correct is True


# ---------- "Học N từ mới" từ trang chủ: dkt_smart xuyên thư viện ----------


def test_dkt_smart_xuyen_thu_vien(client, db_session):
    """Phiên dkt_smart không gắn bộ: nhận từ của nhiều bộ người học sở hữu,
    tìm lại được qua /active?mode=, và KHÔNG bỏ dở phiên ôn tập đang làm."""
    user, headers, ws, items = _setup(db_session, "today.a@example.com")
    ws2 = WordSet(owner_id=user.id, name="Set 2", category="Gen", difficulty="beginner")
    db_session.add(ws2)
    db_session.flush()
    other = Item(word_set_id=ws2.id, word="other", meaning="khác")
    db_session.add(other)
    db_session.commit()

    review = client.post("/api/v1/sessions", json={"mode": "srs_review"}, headers=headers)
    assert review.status_code == 201
    resp = client.post("/api/v1/sessions", json={"mode": "dkt_smart"}, headers=headers)
    assert resp.status_code == 201, resp.text
    sid = resp.json()["id"]
    assert db_session.get(StudySession, review.json()["id"]).status == "in_progress"

    for item in (items[0], other):  # hai bộ khác nhau trong cùng một phiên
        r = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                        json={"item_id": item.id, "is_correct": True, "selection_reason": "band"})
        assert r.status_code == 204, r.text

    active = client.get("/api/v1/sessions/active?mode=dkt_smart", headers=headers).json()
    assert active["session"]["id"] == sid
    assert sorted(active["answered_item_ids"]) == sorted([items[0].id, other.id])
    assert client.get("/api/v1/sessions/active", headers=headers).status_code == 422


def test_dkt_smart_xuyen_thu_vien_tu_choi_tu_nguoi_khac(client, db_session):
    _, headers, _, _ = _setup(db_session, "today.b@example.com")
    _, _, _, foreign = _setup(db_session, "today.c@example.com")
    sid = client.post("/api/v1/sessions", json={"mode": "dkt_smart"}, headers=headers).json()["id"]
    r = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                    json={"item_id": foreign[0].id, "is_correct": True})
    assert r.status_code == 404


def test_modes_khac_van_bat_buoc_word_set(client, db_session):
    _, headers, _, _ = _setup(db_session, "today.d@example.com")
    assert client.post("/api/v1/sessions", json={"mode": "flashcard"}, headers=headers).status_code == 422
