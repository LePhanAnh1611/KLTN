"""UC-84 mở rộng — lộ trình v2 (track chủ đề + cốt lõi) chạy song song v1.

Cam kết cần chứng minh:
1. Thêm v2 KHÔNG đổi gì trên lộ trình của tài khoản v1 (học viên pilot).
2. Mỗi người chỉ thấy chặng (và bộ chặng trong Khám phá) của phiên bản mình.
3. Đồng bộ v1 không tắt chặng v2 và ngược lại; chạy lại không tạo bộ mới.
4. Dữ liệu v2: hai track rời nhau và phủ đủ mọi từ có CEFR của bộ nền.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.learning_stage import LearningStage
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import discover_service, roadmap_seed, roadmap_service
from app.services.auth_service import register_user


def _user(db_session, email, version=None):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    if version is not None:
        u.roadmap_version = version
        db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _study(db_session, user, stage, mastery):
    clone = discover_service.clone_word_set(db_session, user, stage.word_set_id)
    for it in db_session.execute(select(Item).where(Item.word_set_id == clone.id)).scalars():
        db_session.add(KnowledgeState(user_id=user.id, item_id=it.id, mastery=mastery,
                                      last_updated=datetime.now(timezone.utc)))
    db_session.commit()


def _first_stage(db_session, version, level="A1"):
    return db_session.execute(
        select(LearningStage).where(
            LearningStage.roadmap_version == version, LearningStage.cefr_level == level,
            LearningStage.is_active.is_(True),
        ).order_by(LearningStage.order_index)
    ).scalars().first()


def test_new_account_defaults_to_v2(db_session):
    u, _ = _user(db_session, "v2.default@example.com")
    assert u.roadmap_version == 2


def test_adding_v2_leaves_v1_roadmap_unchanged(db_session):
    """Cam kết 1 — chụp lộ trình của người v1 (đang có tiến độ) trước và sau
    khi nạp v2: phải giống hệt từng trường."""
    owner, _ = _user(db_session, "v2.owner1@example.com")
    roadmap_seed.seed_stages(db_session, owner)
    pilot, _ = _user(db_session, "v2.pilot1@example.com", version=1)
    _study(db_session, pilot, _first_stage(db_session, 1), mastery=0.95)
    knowledge_before = db_session.execute(
        select(KnowledgeState.item_id, KnowledgeState.mastery).where(KnowledgeState.user_id == pilot.id)
    ).all()

    before = roadmap_service.get_roadmap(db_session, pilot).model_dump()
    roadmap_seed.seed_stages_v2(db_session, owner)
    roadmap_seed.seed_stages(db_session, owner)          # đồng bộ lại v1 như sync_roadmap
    after = roadmap_service.get_roadmap(db_session, pilot).model_dump()

    assert after == before
    assert all(s["track"] is None for s in after["stages"])
    assert db_session.execute(
        select(KnowledgeState.item_id, KnowledgeState.mastery).where(KnowledgeState.user_id == pilot.id)
    ).all() == knowledge_before


def test_each_user_sees_only_own_version(client, db_session):
    owner, _ = _user(db_session, "v2.owner2@example.com")
    n_v1 = roadmap_seed.seed_stages(db_session, owner)
    n_v2 = roadmap_seed.seed_stages_v2(db_session, owner)
    _, h1 = _user(db_session, "v2.old@example.com", version=1)
    _, h2 = _user(db_session, "v2.new@example.com")

    s1 = client.get("/api/v1/me/roadmap", headers=h1).json()["stages"]
    s2 = client.get("/api/v1/me/roadmap", headers=h2).json()["stages"]
    assert len(s1) == n_v1 and len(s2) == n_v2
    assert not {s["id"] for s in s1} & {s["id"] for s in s2}
    assert {s["track"] for s in s2} == {"topic", "core"}
    assert all(s["topic"] for s in s2 if s["track"] == "topic")
    # Đúng MỘT chặng được gợi ý, và là chặng đầu A1 của v2 (BR-RM-03)
    rec = [s for s in s2 if s["is_recommended"]]
    assert len(rec) == 1 and (rec[0]["cefr_level"], rec[0]["order_index"]) == ("A1", 1)


def test_stage_summary_of_other_version_is_404(client, db_session):
    owner, _ = _user(db_session, "v2.owner3@example.com")
    roadmap_seed.seed_stages(db_session, owner)
    roadmap_seed.seed_stages_v2(db_session, owner)
    _, h1 = _user(db_session, "v2.sum1@example.com", version=1)
    _, h2 = _user(db_session, "v2.sum2@example.com")
    v2_stage = _first_stage(db_session, 2)
    url = f"/api/v1/me/roadmap/stages/{v2_stage.id}/summary"
    assert client.get(url, headers=h2).status_code == 200     # đường dẫn đúng
    assert client.get(url, headers=h1).status_code == 404     # nhưng không phải lộ trình của v1


def test_syncs_do_not_deactivate_each_other_and_are_idempotent(db_session):
    owner, _ = _user(db_session, "v2.owner4@example.com")
    roadmap_seed.seed_stages(db_session, owner)
    n_v2 = roadmap_seed.seed_stages_v2(db_session, owner)

    def snapshot():
        return (
            db_session.execute(select(func.count()).select_from(WordSet)).scalar_one(),
            db_session.execute(select(func.count()).select_from(Item)).scalar_one(),
            {(s.id, s.roadmap_version) for s in db_session.execute(
                select(LearningStage).where(LearningStage.is_active.is_(True))).scalars()},
        )

    first = snapshot()
    assert roadmap_seed.seed_stages_v2(db_session, owner) == n_v2
    roadmap_seed.seed_stages(db_session, owner)
    assert snapshot() == first
    assert {v for _, v in first[2]} == {1, 2}


def test_discover_hides_stage_sets_of_other_version(db_session):
    owner, _ = _user(db_session, "v2.owner5@example.com")
    roadmap_seed.seed_stages(db_session, owner)
    roadmap_seed.seed_stages_v2(db_session, owner)
    v1_user, _ = _user(db_session, "v2.disc1@example.com", version=1)
    v2_user, _ = _user(db_session, "v2.disc2@example.com")
    v1_set, v2_set = _first_stage(db_session, 1).word_set_id, _first_stage(db_session, 2).word_set_id

    def visible(user):
        res = discover_service.list_public(db_session, user, page_size=50, search="A1 ·")
        ids = {c.id for c in res.items}
        page = 2
        while len(ids) < res.total:
            ids |= {c.id for c in discover_service.list_public(
                db_session, user, page=page, page_size=50, search="A1 ·").items}
            page += 1
        return ids

    seen_v1, seen_v2 = visible(v1_user), visible(v2_user)
    assert v1_set in seen_v1 and v2_set not in seen_v1
    assert v2_set in seen_v2 and v1_set not in seen_v2


def test_v2_dataset_partitions_core_dataset():
    """Cam kết 4 — mỗi từ có CEFR của bộ nền nằm ĐÚNG MỘT chặng v2."""
    core = json.loads(roadmap_seed.CORE_SEED_PATH.read_text(encoding="utf-8"))
    v2 = json.loads(roadmap_seed.ROADMAP_V2_PATH.read_text(encoding="utf-8"))
    expected = sorted(
        (it["cefr"], it["word"].lower(), it.get("part_of_speech"))
        for spec in core["word_sets"] for it in spec["items"] if it.get("cefr")
    )
    got = sorted(
        (st["cefr"], it["word"].lower(), it.get("part_of_speech"))
        for st in v2["stages"] for it in st["items"]
    )
    assert got == expected                                  # phủ đủ, không trùng
    for st in v2["stages"]:
        assert all(it["cefr"] == st["cefr"] for it in st["items"])
        if st["track"] == "topic":
            assert 15 <= len(st["items"]) <= 40 and st["topic"]
        else:
            assert st["track"] == "core" and 1 <= len(st["items"]) <= 50
    names = [st["name"] for st in v2["stages"]]
    v1_names = {spec["name"] for spec in core["word_sets"]}
    assert len(set(names)) == len(names) and not set(names) & v1_names
