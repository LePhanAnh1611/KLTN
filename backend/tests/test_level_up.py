"""UC-85 — Nâng cấp trình độ CEFR (BR-LU-01..05)."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.learning_stage import LearningStage
from app.models.notification import Notification
from app.models.user_settings import UserSettings
from app.schemas.auth import RegisterRequest
from app.services import config_service, discover_service, roadmap_seed
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
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


def _set_entry(db_session, user, level):
    row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    row.entry_cefr_level = level
    db_session.commit()


def _download_and_master(db_session, user, stage, mastery: float):
    """Tải bộ của chặng (Q1 snapshot) rồi đặt mastery cho mọi item BẢN SAO (Q2)."""
    clone = discover_service.clone_word_set(db_session, user, stage.word_set_id)
    items = db_session.execute(
        select(Item).where(Item.word_set_id == clone.id, Item.deleted_at.is_(None))
    ).scalars().all()
    for it in items:
        db_session.add(KnowledgeState(user_id=user.id, item_id=it.id, mastery=mastery,
                                      last_updated=datetime.now(timezone.utc)))
    db_session.commit()
    return clone


def _master_level(db_session, user, stages, level: str, mastery: float = 0.95):
    for stage in [s for s in stages if s.cefr_level == level]:
        _download_and_master(db_session, user, stage, mastery)


def _lower_min_items(db_session, count: int = 5):
    """Bộ chặng mẫu chỉ có 12 từ/mức, ít hơn ngưỡng mặc định 20."""
    config_service.set_values(db_session, {"level_up_min_items": count})


def test_not_eligible_when_stages_unfinished(client, db_session):
    """BR-LU-01 — chưa hoàn thành hết chặng của mức hiện tại thì chưa xét."""
    owner, _ = _user(db_session, "lu.owner@example.com")
    user, headers = _user(db_session, "lu.a@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    # chỉ hoàn thành 1 trong 2 chặng A1
    _download_and_master(db_session, user, [s for s in stages if s.cefr_level == "A1"][0], 0.95)

    body = client.get("/api/v1/me/level-up", headers=headers).json()
    assert body["current_level"] == "A1"
    assert body["next_level"] == "A2"
    assert body["eligible"] is False
    assert body["suggestion"] is None
    assert body["stages_total"] == len([s for s in stages if s.cefr_level == "A1"]) and body["stages_mastered"] == 1


def test_not_eligible_when_too_few_items(client, db_session):
    """BR-LU-02 — hoàn thành chặng nhưng chưa đủ số từ tối thiểu thì chưa đủ căn cứ."""
    owner, _ = _user(db_session, "lu.owner2@example.com")
    user, headers = _user(db_session, "lu.b@example.com")
    stages = _stages(db_session, owner)
    # A content administrator can expose just one stage: 50 words < 100.
    a1 = [s for s in stages if s.cefr_level == "A1"]
    for stage in a1[1:]:
        stage.is_active = False
    db_session.commit()
    config_service.set_values(db_session, {"level_up_min_items": 100})
    _master_level(db_session, user, a1[:1], "A1")

    body = client.get("/api/v1/me/level-up", headers=headers).json()
    assert body["stages_mastered"] == body["stages_total"] == 1
    assert body["items_considered"] == 50
    assert body["required_items"] == 100
    assert body["eligible"] is False


def test_not_eligible_when_avg_mastery_low(client, db_session):
    """BR-LU-02 — đủ chặng, đủ từ, nhưng mastery trung bình chưa tới ngưỡng."""
    owner, _ = _user(db_session, "lu.owner3@example.com")
    user, headers = _user(db_session, "lu.c@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    # 0.86 đủ để chặng tính là mastered (M_high 0.85) nhưng dưới ngưỡng nâng mức 0.9
    config_service.set_values(db_session, {"level_up_mastery_threshold": 0.9})
    _master_level(db_session, user, stages, "A1", mastery=0.86)

    body = client.get("/api/v1/me/level-up", headers=headers).json()
    assert body["stages_mastered"] == len([s for s in stages if s.cefr_level == "A1"])
    assert body["eligible"] is False


def test_suggestion_created_with_evidence_and_notification(client, db_session):
    """Đủ điều kiện -> sinh đề xuất kèm bằng chứng + thông báo (UC-61)."""
    owner, _ = _user(db_session, "lu.owner4@example.com")
    user, headers = _user(db_session, "lu.d@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    body = client.get("/api/v1/me/level-up", headers=headers).json()
    assert body["eligible"] is True
    suggestion = body["suggestion"]
    assert suggestion["from_level"] == "A1" and suggestion["to_level"] == "A2"
    assert suggestion["status"] == "pending"
    assert suggestion["items_considered"] == 824
    assert suggestion["avg_mastery"] == 0.95

    notes = db_session.execute(
        select(Notification).where(Notification.user_id == user.id,
                                   Notification.type == "level_up")
    ).scalars().all()
    assert len(notes) == 1
    assert "A2" in notes[0].title and notes[0].link == "/roadmap"


def test_only_one_pending_suggestion(client, db_session):
    """BR-LU-05 — gọi nhiều lần vẫn chỉ một đề xuất chờ."""
    owner, _ = _user(db_session, "lu.owner5@example.com")
    user, headers = _user(db_session, "lu.e@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    first = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]["id"]
    second = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]["id"]
    assert first == second

    notes = db_session.execute(
        select(Notification).where(Notification.user_id == user.id,
                                   Notification.type == "level_up")
    ).scalars().all()
    assert len(notes) == 1   # không spam thông báo mỗi lần mở trang


def test_accept_raises_entry_level_and_regenerates_roadmap(client, db_session):
    """Đồng ý -> entry_cefr_level lên mức mới, lộ trình (UC-84) xuất phát từ đó."""
    owner, _ = _user(db_session, "lu.owner6@example.com")
    user, headers = _user(db_session, "lu.f@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    sid = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]["id"]
    body = client.post(f"/api/v1/me/level-up/{sid}/accept", headers=headers).json()

    assert body["current_level"] == "A2"
    assert body["next_level"] == "B1"
    assert client.get("/api/v1/me/roadmap", headers=headers).json()["entry_level"] == "A2"

    row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    db_session.refresh(row)
    assert row.entry_cefr_level == "A2"


def test_decline_keeps_level_and_never_asks_again(client, db_session):
    """BR-LU-04 — từ chối thì giữ mức cũ và không đề xuất lại đúng cặp mức đó."""
    owner, _ = _user(db_session, "lu.owner7@example.com")
    user, headers = _user(db_session, "lu.g@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    sid = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]["id"]
    body = client.post(f"/api/v1/me/level-up/{sid}/decline", headers=headers).json()

    assert body["current_level"] == "A1"       # giữ nguyên
    assert body["eligible"] is True            # vẫn đủ điều kiện...
    assert body["suggestion"] is None          # ...nhưng không hỏi lại

    # mở lại trang nhiều lần cũng không sinh đề xuất mới
    assert client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"] is None


def test_decide_twice_conflicts(client, db_session):
    """E1 — đề xuất đã quyết định rồi thì không quyết định lại."""
    owner, _ = _user(db_session, "lu.owner8@example.com")
    user, headers = _user(db_session, "lu.h@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    sid = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]["id"]
    assert client.post(f"/api/v1/me/level-up/{sid}/accept", headers=headers).status_code == 200
    assert client.post(f"/api/v1/me/level-up/{sid}/decline", headers=headers).status_code == 409


def test_cannot_decide_someone_elses_suggestion(client, db_session):
    owner, _ = _user(db_session, "lu.owner9@example.com")
    user, headers = _user(db_session, "lu.i@example.com")
    _, other_headers = _user(db_session, "lu.j@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    sid = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]["id"]
    assert client.post(f"/api/v1/me/level-up/{sid}/accept", headers=other_headers).status_code == 404


def test_top_level_has_no_next(client, db_session):
    """BR-LU-03 — đã ở C2 thì không còn mức để nâng."""
    owner, _ = _user(db_session, "lu.owner10@example.com")
    user, headers = _user(db_session, "lu.k@example.com")
    _stages(db_session, owner)
    _set_entry(db_session, user, "C2")

    body = client.get("/api/v1/me/level-up", headers=headers).json()
    assert body["current_level"] == "C2"
    assert body["next_level"] is None
    assert body["eligible"] is False


def test_session_completion_triggers_evaluation(client, db_session, monkeypatch):
    """Học xong một phiên là đề xuất tới ngay, không phải mở trang Lộ trình mới biết."""
    from app.services import dkt_client

    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    owner, _ = _user(db_session, "lu.owner11@example.com")
    user, headers = _user(db_session, "lu.l@example.com")
    stages = _stages(db_session, owner)
    _lower_min_items(db_session)
    _master_level(db_session, user, stages, "A1")

    clone_id = db_session.execute(
        select(Item.word_set_id).join(KnowledgeState, KnowledgeState.item_id == Item.id)
        .where(KnowledgeState.user_id == user.id)
    ).scalars().first()
    item_id = db_session.execute(
        select(Item.id).where(Item.word_set_id == clone_id)
    ).scalars().first()

    sid = client.post("/api/v1/sessions", json={"word_set_id": clone_id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                json={"item_id": item_id, "is_correct": True, "response_time_ms": 900})
    assert client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).status_code == 200

    pending = client.get("/api/v1/me/level-up", headers=headers).json()["suggestion"]
    assert pending is not None and pending["to_level"] == "A2"


def test_level_up_requires_auth(client):
    assert client.get("/api/v1/me/level-up").status_code == 401
    assert client.post("/api/v1/me/level-up/1/accept").status_code == 401
    assert client.post("/api/v1/me/level-up/1/decline").status_code == 401
