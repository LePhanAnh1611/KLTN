"""UC-44 thử thách · UC-56 kết bạn · UC-57 chia sẻ tiến độ ·
UC-70 giám sát mô hình · UC-37/38 luyện viết & sổ tay · lưu kết quả phát âm."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service, dkt_client, llm_client
from app.services.auth_service import register_user


def _setup(db_session, email: str, *, n_items: int = 4, with_examples: bool = False,
           role: str = "learner"):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email.split("@")[0]),
    )
    if role != "learner":
        user.role = role
        db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set0", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [
        Item(word_set_id=ws.id, word=f"word{i}", meaning=f"nghia{i}",
             example=(f"I use word{i} daily." if with_examples else None))
        for i in range(n_items)
    ]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _play(client, headers, ws_id, items, correct=True):
    sid = client.post("/api/v1/sessions", headers=headers,
                      json={"word_set_id": ws_id, "mode": "flashcard"}).json()["id"]
    for it in items:
        client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                    json={"item_id": it.id, "is_correct": correct})
    return client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()


# ---------------------------------------------------------------- UC-44

def test_challenges_progress_reads_live_data(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers, ws, items = _setup(db_session, "ch.a@example.com")
    config_service.set_values(db_session, {
        "challenge_answer_target": 3, "challenge_correct_target": 2,
        "challenge_session_target": 1,
    })

    before = client.get("/api/v1/challenges/today", headers=headers).json()
    assert [i["progress"] for i in before["items"]] == [0, 0, 0]
    assert before["claimable_count"] == 0

    _play(client, headers, ws.id, items[:3])

    after = client.get("/api/v1/challenges/today", headers=headers).json()
    by_code = {i["code"]: i for i in after["items"]}
    assert by_code["answer_words"]["progress"] == 3
    assert by_code["correct_streak"]["progress"] == 2      # đã chặn trần ở target
    assert by_code["finish_session"]["progress"] == 1
    assert all(i["completed"] for i in after["items"])
    assert after["claimable_count"] == 3


def test_claim_awards_xp_and_counts_toward_daily_goal(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    user, headers, ws, items = _setup(db_session, "ch.b@example.com")
    config_service.set_values(db_session, {
        "challenge_session_target": 1, "challenge_session_xp": 25,
    })
    _play(client, headers, ws.id, items[:1])

    xp_before = client.get("/api/v1/progress", headers=headers).json()
    body = client.post("/api/v1/challenges/finish_session/claim", headers=headers).json()
    assert next(i for i in body["items"] if i["code"] == "finish_session")["claimed"] is True

    xp_after = client.get("/api/v1/progress", headers=headers).json()
    assert xp_after["xp"] == xp_before["xp"] + 25
    # XP thưởng phải tính vào mục tiêu XP hôm nay, không thì vòng tiến độ đứng yên
    assert xp_after["today_xp"] == xp_before["today_xp"] + 25


def test_claim_twice_conflicts(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    _, headers, ws, items = _setup(db_session, "ch.c@example.com")
    config_service.set_values(db_session, {"challenge_session_target": 1})
    _play(client, headers, ws.id, items[:1])

    assert client.post("/api/v1/challenges/finish_session/claim",
                       headers=headers).status_code == 200
    assert client.post("/api/v1/challenges/finish_session/claim",
                       headers=headers).status_code == 409


def test_claim_before_completing_is_rejected(client, db_session):
    _, headers, _, _ = _setup(db_session, "ch.d@example.com")
    r = client.post("/api/v1/challenges/answer_words/claim", headers=headers)
    assert r.status_code == 400


def test_claim_unknown_challenge_404(client, db_session):
    _, headers, _, _ = _setup(db_session, "ch.e@example.com")
    assert client.post("/api/v1/challenges/khong_co/claim", headers=headers).status_code == 404


# ---------------------------------------------------------------- UC-56

def test_friend_request_accept_flow(client, db_session):
    a, ha, _, _ = _setup(db_session, "fr.a@example.com")
    b, hb, _, _ = _setup(db_session, "fr.b@example.com")

    state = client.post(f"/api/v1/community/friends/{b.id}", headers=ha).json()
    assert state["status"] == "pending" and state["is_incoming"] is False

    # phía B thấy đây là lời mời ĐẾN
    seen = client.get(f"/api/v1/community/friends/state/{a.id}", headers=hb).json()
    assert seen["status"] == "pending" and seen["is_incoming"] is True

    requests = client.get("/api/v1/community/friends/requests", headers=hb).json()
    assert len(requests) == 1 and requests[0]["user_id"] == a.id

    fid = requests[0]["friendship_id"]
    assert client.post(f"/api/v1/community/friends/requests/{fid}/accept",
                       headers=hb).json()["status"] == "accepted"

    # cả hai phía đều thấy nhau trong danh sách bạn
    assert [f["user_id"] for f in
            client.get("/api/v1/community/friends", headers=ha).json()] == [b.id]
    assert [f["user_id"] for f in
            client.get("/api/v1/community/friends", headers=hb).json()] == [a.id]


def test_decline_allows_sending_again(client, db_session):
    a, ha, _, _ = _setup(db_session, "fr.c@example.com")
    b, hb, _, _ = _setup(db_session, "fr.d@example.com")

    fid = client.post(f"/api/v1/community/friends/{b.id}", headers=ha).json()["friendship_id"]
    client.post(f"/api/v1/community/friends/requests/{fid}/decline", headers=hb)

    assert client.get(f"/api/v1/community/friends/state/{b.id}",
                      headers=ha).json()["status"] == "none"
    # gửi lại được — quan hệ không bị khóa vĩnh viễn
    assert client.post(f"/api/v1/community/friends/{b.id}", headers=ha).status_code == 201


def test_cannot_friend_self_or_duplicate(client, db_session):
    a, ha, _, _ = _setup(db_session, "fr.e@example.com")
    b, _, _, _ = _setup(db_session, "fr.f@example.com")

    assert client.post(f"/api/v1/community/friends/{a.id}", headers=ha).status_code == 400
    assert client.post(f"/api/v1/community/friends/{b.id}", headers=ha).status_code == 201
    assert client.post(f"/api/v1/community/friends/{b.id}", headers=ha).status_code == 409


def test_only_addressee_can_respond(client, db_session):
    a, ha, _, _ = _setup(db_session, "fr.g@example.com")
    b, _, _, _ = _setup(db_session, "fr.h@example.com")
    fid = client.post(f"/api/v1/community/friends/{b.id}", headers=ha).json()["friendship_id"]

    # người GỬI không tự duyệt lời mời của mình được
    assert client.post(f"/api/v1/community/friends/requests/{fid}/accept",
                       headers=ha).status_code == 404


def test_unfriend_clears_relation(client, db_session):
    a, ha, _, _ = _setup(db_session, "fr.i@example.com")
    b, hb, _, _ = _setup(db_session, "fr.j@example.com")
    fid = client.post(f"/api/v1/community/friends/{b.id}", headers=ha).json()["friendship_id"]
    client.post(f"/api/v1/community/friends/requests/{fid}/accept", headers=hb)

    assert client.delete(f"/api/v1/community/friends/{b.id}", headers=ha).status_code == 204
    assert client.get("/api/v1/community/friends", headers=ha).json() == []
    assert client.get(f"/api/v1/community/friends/state/{b.id}",
                      headers=ha).json()["status"] == "none"


def test_search_users_by_name_and_id(client, db_session):
    a, ha, _, _ = _setup(db_session, "srch.alpha@example.com")
    b, _, _, _ = _setup(db_session, "srch.beta@example.com")

    # theo tên (không phân biệt hoa thường), không trả về chính mình
    rows = client.get("/api/v1/community/friends/search", params={"q": "SRCH"},
                      headers=ha).json()
    assert [r["user_id"] for r in rows] == [b.id]
    assert rows[0]["friendship"]["status"] == "none"
    assert "xp" not in rows[0] and "streak_count" not in rows[0]

    # theo ID, có hoặc không có dấu '#'
    for q in (str(b.id), f"#{b.id}"):
        rows = client.get("/api/v1/community/friends/search", params={"q": q},
                          headers=ha).json()
        assert [r["user_id"] for r in rows] == [b.id]

    # trạng thái quan hệ đi kèm để nút hiện đúng chữ
    client.post(f"/api/v1/community/friends/{b.id}", headers=ha)
    rows = client.get("/api/v1/community/friends/search", params={"q": str(b.id)},
                      headers=ha).json()
    assert rows[0]["friendship"]["status"] == "pending"


def test_search_users_ignores_short_terms_and_wildcards(client, db_session):
    a, ha, _, _ = _setup(db_session, "srch.gamma@example.com")
    _setup(db_session, "srch.delta@example.com")

    assert client.get("/api/v1/community/friends/search", params={"q": "s"},
                      headers=ha).json() == []
    # '%' là ký tự thường, không phải "khớp tất cả"
    assert client.get("/api/v1/community/friends/search", params={"q": "%%"},
                      headers=ha).json() == []


def test_friend_request_creates_notification(client, db_session):
    _, ha, _, _ = _setup(db_session, "fr.k@example.com")
    b, hb, _, _ = _setup(db_session, "fr.l@example.com")
    client.post(f"/api/v1/community/friends/{b.id}", headers=ha)

    notes = client.get("/api/v1/notifications", headers=hb).json()
    assert any("kết bạn" in n["title"].lower() for n in notes["items"])


# ---------------------------------------------------------------- UC-57

def test_share_progress_snapshots_numbers(client, db_session):
    user, headers, _, items = _setup(db_session, "sp.a@example.com", n_items=12)
    now = datetime.now(timezone.utc)
    for item in items:
        db_session.add(KnowledgeState(user_id=user.id, item_id=item.id, mastery=0.95, last_updated=now))
        db_session.add_all([Interaction(user_id=user.id, item_id=item.id, is_correct=True, answered_at=now)
                            for _ in range(3)])
    # đăng ký đã tạo sẵn hàng UserProgress -> cập nhật chứ không chèn mới
    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one()
    progress.xp, progress.streak_count, progress.items_mastered = 350, 4, 12
    db_session.commit()

    post = client.post("/api/v1/community/share-progress", headers=headers,
                       json={"message": "Tuần này chăm quá!"}).json()
    assert post["post_type"] == "progress"
    assert "Tuần này chăm quá!" in post["content"]
    assert "350 XP" in post["content"] and "12 từ" in post["content"]

    # số liệu đã chốt vào nội dung: XP đổi sau đó không làm đổi bài đã đăng
    progress.xp = 9999
    db_session.commit()
    feed = client.get("/api/v1/community/posts", headers=headers).json()
    assert "350 XP" in feed["items"][0]["content"]


# ------------------------------------------------- Lưu kết quả phát âm

def test_pronunciation_attempt_saved_without_touching_mastery(client, db_session):
    user, headers, _, items = _setup(db_session, "pr.a@example.com")

    r = client.post("/api/v1/pronunciation/attempts", headers=headers,
                    json={"item_id": items[0].id, "score": 88.5, "transcript": "word zero"})
    assert r.status_code == 201
    assert r.json()["word"] == "word0"

    # điểm phát âm KHÔNG được sinh ra knowledge state
    states = db_session.execute(
        select(KnowledgeState).where(KnowledgeState.user_id == user.id)
    ).scalars().all()
    assert states == []


def test_pronunciation_stats(client, db_session):
    _, headers, _, items = _setup(db_session, "pr.b@example.com")
    for score in (60, 90):
        client.post("/api/v1/pronunciation/attempts", headers=headers,
                    json={"item_id": items[0].id, "score": score})
    client.post("/api/v1/pronunciation/attempts", headers=headers,
                json={"item_id": items[1].id, "score": 70})

    stats = client.get("/api/v1/pronunciation/stats", headers=headers).json()
    assert stats["total_attempts"] == 3
    assert stats["words_practiced"] == 2
    assert stats["best_score"] == 90.0
    assert stats["average_score"] == 73.3
    assert len(stats["recent"]) == 3


def test_pronunciation_rejects_foreign_item(client, db_session):
    _, _, _, items = _setup(db_session, "pr.c@example.com")
    _, other, _, _ = _setup(db_session, "pr.d@example.com")
    assert client.post("/api/v1/pronunciation/attempts", headers=other,
                       json={"item_id": items[0].id, "score": 50}).status_code == 404


def test_pronunciation_best_scores_per_word_set(client, db_session):
    """Thống kê đầu trang Luyện phát âm đọc từ server — F5 không mất tiến độ."""
    _, headers, ws, items = _setup(db_session, "pr.e@example.com")
    for score in (60, 95):
        client.post("/api/v1/pronunciation/attempts", headers=headers,
                    json={"item_id": items[0].id, "score": score})
    client.post("/api/v1/pronunciation/attempts", headers=headers,
                json={"item_id": items[1].id, "score": 70})
    # từ đã xóa mềm không còn được đếm
    items[1].deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    r = client.get(f"/api/v1/pronunciation/best-scores?word_set_id={ws.id}",
                   headers=headers)
    assert r.status_code == 200
    assert r.json() == [{"item_id": items[0].id, "best_score": 95.0, "attempts": 2}]


def test_pronunciation_best_scores_rejects_foreign_word_set(client, db_session):
    _, _, ws, _ = _setup(db_session, "pr.f@example.com")
    _, other, _, _ = _setup(db_session, "pr.g@example.com")
    assert client.get(f"/api/v1/pronunciation/best-scores?word_set_id={ws.id}",
                      headers=other).status_code == 404


# ---------------------------------------------------------------- UC-37/38

def test_writing_prompts_need_examples(client, db_session):
    _, headers, ws, _ = _setup(db_session, "wr.a@example.com", with_examples=False)
    r = client.get(f"/api/v1/writing/prompts?word_set_id={ws.id}", headers=headers)
    assert r.status_code == 400

    _, headers2, ws2, _ = _setup(db_session, "wr.b@example.com", with_examples=True)
    rows = client.get(f"/api/v1/writing/prompts?word_set_id={ws2.id}&limit=2",
                      headers=headers2).json()
    assert len(rows) == 2 and all("word" in r["prompt_vi"] for r in rows)


def test_writing_falls_back_to_heuristic_without_llm(client, db_session, monkeypatch):
    """Không có LLM thì vẫn nộp bài được, và phải nói rõ ai chấm."""
    monkeypatch.setattr(llm_client, "grade_writing", lambda p, a: None)
    _, headers, _, _ = _setup(db_session, "wr.c@example.com")

    good = client.post("/api/v1/writing/submissions", headers=headers, json={
        "prompt_vi": "Đặt một câu tiếng Anh dùng từ “book” (nghĩa: quyển sách).",
        "answer_en": "I read a good book yesterday.",
    }).json()
    assert good["grader"] == "heuristic"
    assert good["score"] == 100.0
    assert good["suggestion"] is None      # không có LLM thì không bịa bản dịch mẫu

    bad = client.post("/api/v1/writing/submissions", headers=headers, json={
        "prompt_vi": "Đặt một câu tiếng Anh dùng từ “book” (nghĩa: quyển sách).",
        "answer_en": "i go",
    }).json()
    assert bad["score"] < 50
    assert "book" in bad["feedback"]


def test_writing_uses_llm_when_available(client, db_session, monkeypatch):
    monkeypatch.setattr(llm_client, "grade_writing", lambda p, a: {
        "score": 82.0, "feedback": "Thiếu mạo từ.", "suggestion": "I read a book.",
    })
    _, headers, _, _ = _setup(db_session, "wr.d@example.com")

    body = client.post("/api/v1/writing/submissions", headers=headers, json={
        "prompt_vi": "Đặt câu với “book”.", "answer_en": "I read book.",
    }).json()
    assert body["grader"] == "llm"
    assert body["score"] == 82.0 and body["suggestion"] == "I read a book."


def test_writing_submissions_listed_newest_first(client, db_session, monkeypatch):
    monkeypatch.setattr(llm_client, "grade_writing", lambda p, a: None)
    _, headers, _, _ = _setup(db_session, "wr.e@example.com")
    for answer in ("First one here.", "Second one here."):
        client.post("/api/v1/writing/submissions", headers=headers,
                    json={"prompt_vi": "Đặt câu.", "answer_en": answer})

    rows = client.get("/api/v1/writing/submissions", headers=headers).json()
    assert [r["answer_en"] for r in rows] == ["Second one here.", "First one here."]


def test_notes_crud_and_search(client, db_session):
    _, headers, _, _ = _setup(db_session, "nt.a@example.com")

    created = client.post("/api/v1/notes", headers=headers, json={
        "text_en": "It rains cats and dogs.", "text_vi": "Mưa như trút nước.",
        "note": "thành ngữ",
    })
    assert created.status_code == 201
    nid = created.json()["id"]

    assert client.patch(f"/api/v1/notes/{nid}", headers=headers,
                        json={"note": "idiom hay dùng"}).json()["note"] == "idiom hay dùng"

    assert len(client.get("/api/v1/notes?q=rains", headers=headers).json()) == 1
    assert client.get("/api/v1/notes?q=khongcogi", headers=headers).json() == []

    assert client.delete(f"/api/v1/notes/{nid}", headers=headers).status_code == 204
    assert client.get("/api/v1/notes", headers=headers).json() == []


def test_notes_are_private(client, db_session):
    _, headers, _, _ = _setup(db_session, "nt.b@example.com")
    _, other, _, _ = _setup(db_session, "nt.c@example.com")
    nid = client.post("/api/v1/notes", headers=headers,
                      json={"text_en": "Hello there."}).json()["id"]

    assert client.get("/api/v1/notes", headers=other).json() == []
    assert client.patch(f"/api/v1/notes/{nid}", headers=other,
                        json={"note": "x"}).status_code == 404
    assert client.delete(f"/api/v1/notes/{nid}", headers=other).status_code == 404


def test_note_cannot_link_someone_elses_submission(client, db_session, monkeypatch):
    monkeypatch.setattr(llm_client, "grade_writing", lambda p, a: None)
    _, headers, _, _ = _setup(db_session, "nt.d@example.com")
    _, other, _, _ = _setup(db_session, "nt.e@example.com")
    sid = client.post("/api/v1/writing/submissions", headers=headers,
                      json={"prompt_vi": "Đặt câu.", "answer_en": "A sentence here."}).json()["id"]

    assert client.post("/api/v1/notes", headers=other, json={
        "text_en": "Stolen.", "submission_id": sid,
    }).status_code == 404


# ---------------------------------------------------------------- UC-70

def test_model_health_marks_small_sample_unreliable(client, db_session):
    _, admin, _, _ = _setup(db_session, "mh.a@example.com", role="admin")
    body = client.get("/api/v1/admin/model-health", headers=admin).json()
    assert body["reliable"] is False
    assert body["accuracy"] is None and body["brier"] is None   # không trả 0 gây hiểu nhầm
    assert "Cần tối thiểu" in body["note"]


def test_model_health_computes_on_real_data(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.9 for x in t})
    _, admin, ws, items = _setup(db_session, "mh.b@example.com", n_items=4, role="admin")
    config_service.set_values(db_session, {"challenge_session_target": 1})

    for _ in range(6):
        _play(client, admin, ws.id, items)      # 24 lượt trả lời đúng

    body = client.get("/api/v1/admin/model-health", headers=admin).json()
    assert body["reliable"] is True
    assert body["sample_size"] >= 20
    assert body["accuracy"] == 1.0              # mastery 0.9 -> dự đoán đúng, thực tế đúng
    assert body["brier"] < 0.02


def test_model_health_snapshot_and_history(client, db_session):
    _, admin, _, _ = _setup(db_session, "mh.c@example.com", role="admin")

    assert client.post("/api/v1/admin/model-health/snapshot", headers=admin).status_code == 200
    history = client.get("/api/v1/admin/model-health/history", headers=admin).json()
    # mẫu chưa đủ vẫn chốt được coverage — chỉ số này luôn có nghĩa
    assert [p["metric"] for p in history] == ["coverage"]


def test_model_health_requires_permission(client, db_session):
    _, learner, _, _ = _setup(db_session, "mh.d@example.com")
    assert client.get("/api/v1/admin/model-health", headers=learner).status_code == 403


def test_new_endpoints_require_auth(client):
    for path in ("/api/v1/challenges/today", "/api/v1/community/friends",
                 "/api/v1/notes", "/api/v1/pronunciation/stats",
                 "/api/v1/writing/submissions"):
        assert client.get(path).status_code == 401, path
