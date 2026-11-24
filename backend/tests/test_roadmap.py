"""UC-84 — Lộ trình học cá nhân hóa (BR-RM-01..05)."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.learning_stage import LearningStage
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import discover_service, dkt_client, roadmap_seed
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
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
    """Tải bộ của chặng về (Q1 snapshot) rồi đặt mastery cho mọi item bản sao."""
    clone = discover_service.clone_word_set(db_session, user, stage.word_set_id)
    items = db_session.execute(
        select(Item).where(Item.word_set_id == clone.id, Item.deleted_at.is_(None))
    ).scalars().all()
    for it in items:
        db_session.add(KnowledgeState(user_id=user.id, item_id=it.id, mastery=mastery,
                                      last_updated=datetime.now(timezone.utc)))
    db_session.commit()
    return clone


def test_empty_roadmap(client, db_session):
    """Ngoại lệ — Admin chưa tạo chặng nào."""
    _, headers = _user(db_session, "rm.a@example.com")
    body = client.get("/api/v1/me/roadmap", headers=headers).json()
    assert body["stages"] == [] and body["entry_level"] == "A1"


def test_user_without_placement_defaults_a1(client, db_session):
    """Bước 3 mục 5 — chưa làm placement thì điểm xuất phát là A1, không có
    chặng nào được coi là 'achieved'."""
    owner, _ = _user(db_session, "rm.b1@example.com")
    _stages(db_session, owner)
    _, headers = _user(db_session, "rm.b2@example.com")

    body = client.get("/api/v1/me/roadmap", headers=headers).json()
    assert body["entry_level"] == "A1"
    assert "achieved" not in {s["state"] for s in body["stages"]}
    assert len(body["stages"]) == len(_stages(db_session, owner))


def test_stages_sorted_by_level_then_order(client, db_session):
    owner, _ = _user(db_session, "rm.c1@example.com")
    _stages(db_session, owner)
    _, headers = _user(db_session, "rm.c2@example.com")

    stages = client.get("/api/v1/me/roadmap", headers=headers).json()["stages"]
    keys = [(s["cefr_level"], s["order_index"]) for s in stages]
    assert keys == sorted(keys)


def test_entry_level_marks_lower_stages_achieved(client, db_session):
    """BR-RM-02 — chặng dưới trình độ đầu vào & chưa động tới -> achieved."""
    owner, _ = _user(db_session, "rm.d1@example.com")
    _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.d2@example.com")
    _set_entry(db_session, learner, "B1")

    body = client.get("/api/v1/me/roadmap", headers=headers).json()
    assert body["entry_level"] == "B1"
    by_level = {}
    for s in body["stages"]:
        by_level.setdefault(s["cefr_level"], []).append(s["state"])

    assert set(by_level["A1"]) == {"achieved"}
    assert set(by_level["A2"]) == {"achieved"}
    assert "achieved" not in by_level["B1"]      # chặng ngang trình độ thì vẫn phải học


def test_exactly_one_recommended_stage(client, db_session):
    """BR-RM-03 — luôn CHỈ có một chặng is_recommended."""
    owner, _ = _user(db_session, "rm.e1@example.com")
    _stages(db_session, owner)

    for i, entry in enumerate(["A1", "A2", "B1"]):
        learner, headers = _user(db_session, f"rm.e2{i}@example.com")
        _set_entry(db_session, learner, entry)

        stages = client.get("/api/v1/me/roadmap", headers=headers).json()["stages"]
        recommended = [s for s in stages if s["is_recommended"]]
        assert len(recommended) == 1, f"entry={entry} -> {len(recommended)} chặng gợi ý"
        assert recommended[0]["state"] == "current"


def test_recommended_is_earliest_unfinished_from_entry(client, db_session):
    """Với entry A2, chặng gợi ý là chặng A2 đầu tiên (không phải A1)."""
    owner, _ = _user(db_session, "rm.f1@example.com")
    _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.f2@example.com")
    _set_entry(db_session, learner, "A2")

    stages = client.get("/api/v1/me/roadmap", headers=headers).json()["stages"]
    current = next(s for s in stages if s["is_recommended"])
    assert current["cefr_level"] == "A2" and current["order_index"] == 1


def test_stages_after_current_are_locked(client, db_session):
    """BR-RM-04 — chặng sau chặng gợi ý bị khóa."""
    owner, _ = _user(db_session, "rm.g1@example.com")
    _stages(db_session, owner)
    _, headers = _user(db_session, "rm.g2@example.com")

    stages = client.get("/api/v1/me/roadmap", headers=headers).json()["stages"]
    current_at = next(i for i, s in enumerate(stages) if s["is_recommended"])
    assert all(s["state"] == "locked" for s in stages[current_at + 1:])


def test_mastered_stage_and_progress(client, db_session, monkeypatch):
    """BR-RM-01 — đủ tỉ lệ item đạt M_high thì chặng là 'mastered'; mastery đọc
    theo item BẢN SAO (Q2)."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    owner, _ = _user(db_session, "rm.h1@example.com")
    stages = _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.h2@example.com")

    _download_and_master(db_session, learner, stages[0], mastery=0.95)

    body = client.get("/api/v1/me/roadmap", headers=headers).json()
    first = body["stages"][0]
    assert first["state"] == "mastered"
    assert first["items_mastered"] == first["items_total"]
    assert first["progress_pct"] == 100.0
    assert first["user_word_set_id"] is not None      # đã có bản sao trong thư viện

    # chặng gợi ý dịch sang chặng kế tiếp
    assert body["stages"][1]["is_recommended"] is True


def test_in_progress_stage(client, db_session, monkeypatch):
    """BR-RM-05 — đã bắt đầu nhưng chưa đạt ngưỡng -> in_progress kèm %."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    owner, _ = _user(db_session, "rm.i1@example.com")
    stages = _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.i2@example.com")

    clone = discover_service.clone_word_set(db_session, learner, stages[0].word_set_id)
    items = db_session.execute(
        select(Item).where(Item.word_set_id == clone.id)
    ).scalars().all()
    # chỉ 2/6 item đạt ngưỡng -> dưới tỉ lệ 0.8
    for i, it in enumerate(items):
        db_session.add(KnowledgeState(user_id=learner.id, item_id=it.id,
                                      mastery=0.95 if i < 2 else 0.3,
                                      last_updated=datetime.now(timezone.utc)))
    db_session.commit()

    first = client.get("/api/v1/me/roadmap", headers=headers).json()["stages"][0]
    assert first["state"] in {"current", "in_progress"}
    assert first["items_mastered"] == 2 and first["items_total"] == len(items)
    assert first["progress_pct"] == round(2 / len(items) * 100, 1)
    # Vòng tiến độ đo theo mục tiêu qua chặng (80%), và ghi nhận từ đang học dở
    import math
    assert first["items_needed"] == math.ceil(round(0.8 * len(items), 6))
    assert first["items_learning"] == len(items) - 2


def test_progress_ignores_original_set_mastery(client, db_session, monkeypatch):
    """Q1/Q2 — mastery của người học nằm ở item BẢN SAO; chưa tải thì chặng chưa
    có tiến độ dù bộ gốc có item."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    owner, _ = _user(db_session, "rm.j1@example.com")
    stages = _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.j2@example.com")

    # đặt mastery lên item của bộ GỐC (không phải bản sao) -> không được tính
    origin_items = db_session.execute(
        select(Item).where(Item.word_set_id == stages[0].word_set_id)
    ).scalars().all()
    for it in origin_items:
        db_session.add(KnowledgeState(user_id=learner.id, item_id=it.id, mastery=0.99,
                                      last_updated=datetime.now(timezone.utc)))
    db_session.commit()

    first = client.get("/api/v1/me/roadmap", headers=headers).json()["stages"][0]
    assert first["items_mastered"] == 0
    assert first["user_word_set_id"] is None
    assert first["state"] != "mastered"


def test_thresholds_are_configurable(client, db_session, monkeypatch):
    """BR-RM-01 lấy ngưỡng từ cấu hình hệ thống (UC-81)."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.7 for x in t})
    from app.services import config_service

    owner, _ = _user(db_session, "rm.k1@example.com")
    stages = _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.k2@example.com")
    _download_and_master(db_session, learner, stages[0], mastery=0.87)

    assert client.get("/api/v1/me/roadmap", headers=headers).json()["stages"][0]["state"] == "mastered"

    config_service.set_values(db_session, {"stage_mastery_high": 0.95})
    assert client.get("/api/v1/me/roadmap", headers=headers).json()["stages"][0]["state"] != "mastered"


def test_inactive_stage_hidden(client, db_session):
    owner, _ = _user(db_session, "rm.l1@example.com")
    stages = _stages(db_session, owner)
    stages[0].is_active = False
    db_session.commit()

    _, headers = _user(db_session, "rm.l2@example.com")
    body = client.get("/api/v1/me/roadmap", headers=headers).json()
    assert all(s["id"] != stages[0].id for s in body["stages"])


def test_roadmap_requires_auth(client):
    assert client.get("/api/v1/me/roadmap").status_code == 401


def test_c1_entry_stays_at_c1_after_optional_lower_study(client, db_session):
    owner, _ = _user(db_session, "rm.skip.owner@example.com")
    stages = _stages(db_session, owner)
    learner, headers = _user(db_session, "rm.skip.learner@example.com")
    _set_entry(db_session, learner, "C1")
    _download_and_master(db_session, learner, stages[0], mastery=0.3)
    body = client.get("/api/v1/me/roadmap", headers=headers).json()
    current = next(s for s in body["stages"] if s["is_recommended"])
    assert (current["cefr_level"], current["order_index"]) == ("C1", 1)
    assert all(s["is_skipped"] for s in body["stages"] if s["cefr_level"] in ("A1", "A2", "B1", "B2"))
    assert not current["is_skipped"]


def test_core_stage_sync_is_idempotent_and_preserves_old_sets(db_session):
    owner, _ = _user(db_session, "rm.sync.owner@example.com")
    old_set = WordSet(owner_id=owner.id, name="Legacy", is_public=True)
    db_session.add(old_set)
    db_session.flush()
    old = LearningStage(title="Legacy", cefr_level="A1", order_index=1, word_set_id=old_set.id)
    db_session.add(old)
    db_session.commit()
    count = roadmap_seed.seed_stages(db_session, owner)
    active = db_session.execute(select(LearningStage).where(LearningStage.is_active.is_(True))).scalars().all()
    ids = {s.id for s in active}
    assert not old.is_active and db_session.get(WordSet, old_set.id) is not None
    assert {s.cefr_level for s in active} == {"A1", "A2", "B1", "B2", "C1", "C2"}
    assert roadmap_seed.seed_stages(db_session, owner) == count
    assert ids == {s.id for s in db_session.execute(select(LearningStage).where(LearningStage.is_active.is_(True))).scalars()}
