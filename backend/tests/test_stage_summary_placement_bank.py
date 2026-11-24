"""Tổng kết chặng lộ trình (UC-84) · Quản trị ngân hàng câu hỏi đầu vào (UC-11)."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.learning_stage import LearningStage
from app.models.placement import PlacementQuestion
from app.schemas.auth import RegisterRequest
from app.services import config_service, discover_service, dkt_client, roadmap_seed
from app.services.auth_service import register_user


def _user(db_session, email, role="learner"):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    if role != "learner":
        u.role = role
        db_session.commit()
    # Các test trong file này kiểm lộ trình v1 (seed_stages) — tức tài khoản có
    # từ trước migration rmv2. Lộ trình v2 có test riêng: test_roadmap_v2.py.
    u.roadmap_version = 1
    db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _stages(db_session, owner):
    roadmap_seed.seed_stages(db_session, owner)
    return db_session.execute(
        select(LearningStage).order_by(LearningStage.cefr_level, LearningStage.order_index)
    ).scalars().all()


def _download(db_session, user, stage):
    return discover_service.clone_word_set(db_session, user, stage.word_set_id)


def _set_mastery(db_session, user, word_set_id, values: list[float]):
    """Gán mastery lần lượt cho các item của bộ (thiếu thì bỏ qua item còn lại)."""
    items = db_session.execute(
        select(Item).where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
        .order_by(Item.id)
    ).scalars().all()
    for item, value in zip(items, values):
        db_session.add(KnowledgeState(user_id=user.id, item_id=item.id, mastery=value,
                                      last_updated=datetime.now(timezone.utc)))
    db_session.commit()
    return items


# ------------------------------------------------ Tổng kết chặng (UC-84)

def test_stage_summary_reports_progress_and_word_split(client, db_session):
    owner, _ = _user(db_session, "ss.owner@example.com")
    user, headers = _user(db_session, "ss.a@example.com")
    stage = _stages(db_session, owner)[0]
    clone = _download(db_session, user, stage)
    # 6 từ: 4 nắm chắc, 2 dưới ngưỡng điểm yếu (0.6)
    _set_mastery(db_session, user, clone.id, [0.95, 0.92, 0.90, 0.88, 0.30, 0.10])

    body = client.get(f"/api/v1/me/roadmap/stages/{stage.id}/summary", headers=headers).json()

    assert body["stage_id"] == stage.id
    assert body["title"] == stage.title
    assert body["items_total"] == len(db_session.execute(select(Item).where(Item.word_set_id == clone.id)).scalars().all())
    assert body["items_mastered"] == 4          # >= stage_mastery_high 0.85

    # điểm mạnh xếp giảm dần, điểm yếu chỉ gồm từ THỰC SỰ dưới ngưỡng
    assert [w["mastery"] for w in body["strongest"]] == [0.95, 0.92, 0.9, 0.88, 0.3]
    assert [w["mastery"] for w in body["weakest"]] == [0.1, 0.3]


def test_stage_summary_has_no_weak_words_when_all_strong(client, db_session):
    """Chặng hoàn hảo thì cột 'cần ôn lại' rỗng, không bịa ra điểm yếu."""
    owner, _ = _user(db_session, "ss.owner2@example.com")
    user, headers = _user(db_session, "ss.b@example.com")
    stage = _stages(db_session, owner)[0]
    clone = _download(db_session, user, stage)
    _set_mastery(db_session, user, clone.id, [0.95] * 100)

    body = client.get(f"/api/v1/me/roadmap/stages/{stage.id}/summary", headers=headers).json()
    assert body["weakest"] == []
    assert body["is_complete"] is True
    assert body["state"] == "mastered"


def test_stage_summary_counts_answers_from_interactions(client, db_session, monkeypatch):
    """answers_* đọc từ INTERACTION (quá trình), khác items_* đọc từ mastery (hiện tại)."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.9 for x in t})
    owner, _ = _user(db_session, "ss.owner3@example.com")
    user, headers = _user(db_session, "ss.c@example.com")
    stage = _stages(db_session, owner)[0]
    clone = _download(db_session, user, stage)
    items = _set_mastery(db_session, user, clone.id, [0.9] * 6)

    sid = client.post("/api/v1/sessions", headers=headers,
                      json={"word_set_id": clone.id, "mode": "flashcard"}).json()["id"]
    for item, correct in zip(items[:3], [True, True, False]):
        client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                    json={"item_id": item.id, "is_correct": correct})
    client.post(f"/api/v1/sessions/{sid}/complete", headers=headers)

    body = client.get(f"/api/v1/me/roadmap/stages/{stage.id}/summary", headers=headers).json()
    assert body["answers_total"] == 3
    assert body["answers_correct"] == 2
    assert round(body["accuracy"], 3) == round(2 / 3, 3)


def test_stage_summary_points_to_next_stage(client, db_session):
    owner, _ = _user(db_session, "ss.owner4@example.com")
    user, headers = _user(db_session, "ss.d@example.com")
    stages = _stages(db_session, owner)
    clone = _download(db_session, user, stages[0])
    _set_mastery(db_session, user, clone.id, [0.95] * 100)

    body = client.get(f"/api/v1/me/roadmap/stages/{stages[0].id}/summary",
                      headers=headers).json()
    assert body["next_stage_id"] is not None
    assert body["next_stage_id"] != stages[0].id
    assert body["next_stage_title"]


def test_stage_summary_when_set_not_downloaded(client, db_session):
    """Chưa tải bộ của chặng -> chưa có gì để tổng kết, nhưng không được lỗi."""
    owner, _ = _user(db_session, "ss.owner5@example.com")
    _, headers = _user(db_session, "ss.e@example.com")
    stage = _stages(db_session, owner)[0]

    body = client.get(f"/api/v1/me/roadmap/stages/{stage.id}/summary", headers=headers).json()
    assert body["items_mastered"] == 0
    assert body["answers_total"] == 0
    assert body["strongest"] == [] and body["weakest"] == []


def test_stage_summary_unknown_stage_404(client, db_session):
    _, headers = _user(db_session, "ss.f@example.com")
    assert client.get("/api/v1/me/roadmap/stages/999999/summary",
                      headers=headers).status_code == 404


# ------------------------- Ngân hàng câu hỏi đầu vào (UC-11, Admin)

def _admin(db_session, email):
    return _user(db_session, email, role="admin")


def test_admin_crud_placement_question(client, db_session):
    _, headers = _admin(db_session, "pq.a@example.com")

    created = client.post("/api/v1/admin/placement-questions", headers=headers, json={
        "cefr_level": "B1", "word": "resilient", "correct_meaning": "kiên cường",
        "distractors": ["mỏng manh", "rực rỡ", "chậm chạp"],
    })
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    assert created.json()["is_active"] is True

    updated = client.patch(f"/api/v1/admin/placement-questions/{qid}", headers=headers,
                           json={"is_active": False, "cefr_level": "B2"}).json()
    assert updated["is_active"] is False and updated["cefr_level"] == "B2"

    assert client.delete(f"/api/v1/admin/placement-questions/{qid}",
                         headers=headers).status_code == 204
    assert db_session.get(PlacementQuestion, qid) is None


def test_admin_rejects_duplicate_options(client, db_session):
    """E1 — nhiễu trùng đáp án đúng thì câu hỏi có 2 đáp án đúng."""
    _, headers = _admin(db_session, "pq.b@example.com")
    r = client.post("/api/v1/admin/placement-questions", headers=headers, json={
        "cefr_level": "A1", "word": "cat", "correct_meaning": "con mèo",
        "distractors": ["con mèo", "con chó", "con gà"],
    })
    assert r.status_code == 400
    assert "khác nhau" in r.json()["detail"]


def test_admin_requires_exactly_three_distractors(client, db_session):
    _, headers = _admin(db_session, "pq.c@example.com")
    r = client.post("/api/v1/admin/placement-questions", headers=headers, json={
        "cefr_level": "A1", "word": "cat", "correct_meaning": "con mèo",
        "distractors": ["con chó"],
    })
    assert r.status_code == 422


def test_admin_bank_stats_covers_all_levels(client, db_session):
    """Mức chưa có câu nào vẫn phải xuất hiện — đó chính là chỗ Admin cần thấy."""
    _, headers = _admin(db_session, "pq.d@example.com")
    client.post("/api/v1/admin/placement-questions", headers=headers, json={
        "cefr_level": "A1", "word": "cat", "correct_meaning": "con mèo",
        "distractors": ["con chó", "con gà", "con cá"],
    })
    client.post("/api/v1/admin/placement-questions", headers=headers, json={
        "cefr_level": "A1", "word": "dog", "correct_meaning": "con chó",
        "distractors": ["con mèo", "con gà", "con cá"], "is_active": False,
    })

    stats = client.get("/api/v1/admin/placement-questions/stats", headers=headers).json()
    assert [row["cefr_level"] for row in stats] == ["A1", "A2", "B1", "B2", "C1", "C2"]

    a1 = next(row for row in stats if row["cefr_level"] == "A1")
    assert a1["total_count"] == 2 and a1["active_count"] == 1
    assert all(row["total_count"] == 0 for row in stats if row["cefr_level"] != "A1")


def test_inactive_question_not_served_to_learner(client, db_session):
    """Tắt câu hỏi thì bài kiểm tra không lấy ra nữa."""
    _, admin_headers = _admin(db_session, "pq.e@example.com")
    _, learner = _user(db_session, "pq.f@example.com")

    qid = client.post("/api/v1/admin/placement-questions", headers=admin_headers, json={
        "cefr_level": "A1", "word": "cat", "correct_meaning": "con mèo",
        "distractors": ["con chó", "con gà", "con cá"],
    }).json()["id"]

    served = client.get("/api/v1/placement/questions", headers=learner).json()
    assert qid in {q["id"] for q in served}

    client.patch(f"/api/v1/admin/placement-questions/{qid}", headers=admin_headers,
                 json={"is_active": False})
    after = client.get("/api/v1/placement/questions", headers=learner)
    # Ngân hàng rỗng -> endpoint báo lỗi có chủ đích; nếu trả 200 thì phải vắng câu vừa tắt
    assert after.status_code != 200 or qid not in {q["id"] for q in after.json()}


def test_admin_list_filters_by_level(client, db_session):
    _, headers = _admin(db_session, "pq.g@example.com")
    for level in ("A1", "C1"):
        client.post("/api/v1/admin/placement-questions", headers=headers, json={
            "cefr_level": level, "word": f"w{level}", "correct_meaning": f"m{level}",
            "distractors": ["a", "b", "c"],
        })

    rows = client.get("/api/v1/admin/placement-questions?cefr_level=C1", headers=headers).json()
    assert [r["word"] for r in rows] == ["wC1"]
    assert rows[0]["correct_meaning"] == "mC1"      # Admin thấy đáp án đúng


def test_learner_cannot_touch_placement_bank(client, db_session):
    _, learner = _user(db_session, "pq.h@example.com")
    assert client.get("/api/v1/admin/placement-questions", headers=learner).status_code == 403
    assert client.post("/api/v1/admin/placement-questions", headers=learner, json={
        "cefr_level": "A1", "word": "x", "correct_meaning": "y",
        "distractors": ["a", "b", "c"],
    }).status_code == 403


def test_placement_bank_requires_auth(client):
    assert client.get("/api/v1/admin/placement-questions").status_code == 401
    assert client.get("/api/v1/me/roadmap/stages/1/summary").status_code == 401


def test_stage_summary_weak_threshold_from_config(client, db_session):
    """Ngưỡng 'cần ôn lại' dùng chung với UC-86, lấy từ cấu hình."""
    owner, _ = _user(db_session, "ss.owner6@example.com")
    user, headers = _user(db_session, "ss.g@example.com")
    stage = _stages(db_session, owner)[0]
    clone = _download(db_session, user, stage)
    _set_mastery(db_session, user, clone.id, [0.95, 0.95, 0.95, 0.95, 0.55, 0.25])

    url = f"/api/v1/me/roadmap/stages/{stage.id}/summary"
    assert len(client.get(url, headers=headers).json()["weakest"]) == 2

    config_service.set_values(db_session, {"weak_mastery_threshold": 0.3})
    assert [w["mastery"] for w in client.get(url, headers=headers).json()["weakest"]] == [0.25]
