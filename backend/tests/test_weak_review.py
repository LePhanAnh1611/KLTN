"""UC-86 — phiên ôn tập điểm yếu (từ mastery thấp, không phụ thuộc lịch ôn)."""
from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service
from app.services.auth_service import register_user


def _setup(db_session, email: str, n_sets: int = 1, n_items: int = 4):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    sets = []
    for s in range(n_sets):
        ws = WordSet(owner_id=user.id, name=f"Set{s}", category="Gen", difficulty="beginner")
        db_session.add(ws)
        db_session.flush()
        items = [Item(word_set_id=ws.id, word=f"w{s}_{i}", meaning=f"m{s}_{i}")
                 for i in range(n_items)]
        db_session.add_all(items)
        db_session.commit()
        for it in items:
            db_session.refresh(it)
        sets.append((ws, items))
    return user, headers, sets


def _mastery(db_session, user_id: int, item_id: int, value: float):
    db_session.add(KnowledgeState(
        user_id=user_id, item_id=item_id, mastery=value,
        last_updated=datetime.now(timezone.utc),
    ))
    db_session.commit()


def test_weak_items_sorted_and_filtered(client, db_session):
    """Chỉ trả từ dưới ngưỡng, yếu nhất lên trước."""
    user, headers, sets = _setup(db_session, "weak.a@example.com")
    _, items = sets[0]
    _mastery(db_session, user.id, items[0].id, 0.95)   # đã thuộc -> loại
    _mastery(db_session, user.id, items[1].id, 0.20)   # yếu nhất
    _mastery(db_session, user.id, items[2].id, 0.45)
    _mastery(db_session, user.id, items[3].id, 0.60)   # đúng bằng ngưỡng -> loại

    rows = client.get("/api/v1/reviews/weak", headers=headers).json()
    assert [r["word"] for r in rows] == ["w0_1", "w0_2"]
    assert rows[0]["mastery"] == 0.2
    assert rows[0]["word_set_name"] == "Set0"


def test_weak_ignores_review_schedule(client, db_session):
    """Điểm khác UC-33: từ vừa trả lời sai chưa "đến hạn" nhưng vẫn phải hiện ra."""
    user, headers, sets = _setup(db_session, "weak.b@example.com")
    _, items = sets[0]
    _mastery(db_session, user.id, items[0].id, 0.15)
    db_session.add(ReviewSchedule(
        user_id=user.id, item_id=items[0].id,
        next_review_at=datetime.now(timezone.utc) + timedelta(days=3), interval_days=3,
    ))
    db_session.commit()

    assert client.get("/api/v1/reviews/due", headers=headers).json() == []
    weak = client.get("/api/v1/reviews/weak", headers=headers).json()
    assert [r["word"] for r in weak] == ["w0_0"]


def test_weak_across_word_sets(client, db_session):
    user, headers, sets = _setup(db_session, "weak.c@example.com", n_sets=2, n_items=1)
    _mastery(db_session, user.id, sets[0][1][0].id, 0.30)
    _mastery(db_session, user.id, sets[1][1][0].id, 0.10)

    rows = client.get("/api/v1/reviews/weak", headers=headers).json()
    assert [r["word"] for r in rows] == ["w1_0", "w0_0"]   # xuyên thư viện, yếu nhất trước


def test_weak_respects_limit_and_config(client, db_session):
    user, headers, sets = _setup(db_session, "weak.d@example.com", n_items=4)
    _, items = sets[0]
    for i, value in enumerate([0.1, 0.2, 0.3, 0.4]):
        _mastery(db_session, user.id, items[i].id, value)

    assert len(client.get("/api/v1/reviews/weak?limit=2", headers=headers).json()) == 2

    # UC-81: số từ mỗi phiên lấy từ cấu hình, không hardcode
    config_service.set_values(db_session, {"weak_session_size": 3})
    assert len(client.get("/api/v1/reviews/weak", headers=headers).json()) == 3


def test_weak_threshold_from_config(client, db_session):
    """Hạ ngưỡng điểm yếu thì danh sách co lại — trang Tiến độ dùng chung ngưỡng này."""
    user, headers, sets = _setup(db_session, "weak.e@example.com", n_items=2)
    _, items = sets[0]
    _mastery(db_session, user.id, items[0].id, 0.25)
    _mastery(db_session, user.id, items[1].id, 0.55)

    assert len(client.get("/api/v1/reviews/weak", headers=headers).json()) == 2

    config_service.set_values(db_session, {"weak_mastery_threshold": 0.3})

    weak = client.get("/api/v1/reviews/weak", headers=headers).json()
    assert [r["word"] for r in weak] == ["w0_0"]
    # cùng ngưỡng -> trang Tiến độ (UC-40) cũng chỉ còn 1 từ điểm yếu
    progress = client.get("/api/v1/progress", headers=headers).json()
    assert [w["word"] for w in progress["weak_items"]] == ["w0_0"]


def test_weak_empty_when_nothing_learned(client, db_session):
    _, headers, _ = _setup(db_session, "weak.f@example.com")
    assert client.get("/api/v1/reviews/weak", headers=headers).json() == []


def test_weak_requires_auth(client):
    assert client.get("/api/v1/reviews/weak").status_code == 401


def test_weak_session_is_creatable_and_records_answers(client, db_session, monkeypatch):
    """Phiên ôn điểm yếu phải mở được và trả lời được từ ở BẤT KỲ bộ nào.

    Đây là chỗ bản đầu bị hở: endpoint /reviews/weak chạy đúng nhưng
    SessionCreateRequest chưa nhận mode 'weak_review' nên bấm nút là 422.
    """
    from app.services import dkt_client

    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.4 for x in t})
    user, headers, sets = _setup(db_session, "weak.g@example.com", n_sets=2, n_items=1)
    _mastery(db_session, user.id, sets[0][1][0].id, 0.20)
    _mastery(db_session, user.id, sets[1][1][0].id, 0.30)

    created = client.post("/api/v1/sessions", json={"mode": "weak_review"}, headers=headers)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    assert created.json()["word_set_id"] is None      # xuyên thư viện

    for _, items in sets:
        answered = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
            "item_id": items[0].id, "is_correct": True, "response_time_ms": 800,
        })
        assert answered.status_code == 204, answered.text

    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()
    assert summary["total_answered"] == 2 and summary["correct_count"] == 2
