"""UC-92 — đường cong học tập của một từ.

Điểm cần canh: đường cong dựng từ `INTERACTION.predicted_mastery`, tức giá trị
mô hình nắm giữ **trước** mỗi lượt trả lời. Nếu lấy mastery hiện tại rồi vẽ
ngược lại thì đó là hậu nghiệm, không phải đường học tập.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.interaction import Interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _setup(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="S", category="G", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    item = Item(word_set_id=ws.id, word="habitat", meaning="môi trường sống",
                part_of_speech="noun")
    db_session.add(item)
    db_session.commit()
    return user, headers, item


def _answer(db_session, user, item, *, mastery, correct, minutes, source="model",
            fmt="quiz"):
    db_session.add(Interaction(
        user_id=user.id, item_id=item.id, is_correct=correct,
        predicted_mastery=mastery, prediction_source=source, exercise_format=fmt,
        answered_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
    ))


def test_duong_cong_theo_dung_thu_tu_thoi_gian(client, db_session):
    user, headers, item = _setup(db_session, "mh.a@example.com")
    # cố tình thêm KHÔNG theo thứ tự để bắt lỗi thiếu ORDER BY
    _answer(db_session, user, item, mastery=0.62, correct=True, minutes=20)
    _answer(db_session, user, item, mastery=0.41, correct=False, minutes=0)
    _answer(db_session, user, item, mastery=0.55, correct=True, minutes=10)
    db_session.add(KnowledgeState(user_id=user.id, item_id=item.id, mastery=0.71,
                                  last_updated=datetime.now(timezone.utc)))
    db_session.commit()

    body = client.get(f"/api/v1/progress/items/{item.id}/mastery-history",
                      headers=headers).json()

    assert body["word"] == "habitat"
    assert [p["mastery"] for p in body["points"]] == [0.41, 0.55, 0.62]
    assert [p["is_correct"] for p in body["points"]] == [False, True, True]
    assert body["current_mastery"] == 0.71     # điểm cuối: sau lượt gần nhất
    assert body["total_answers"] == 3
    assert body["mastered_threshold"] == 0.9   # BR-01, để vẽ vạch "đã thuộc"


def test_luot_chua_co_du_doan_tra_None_chu_khong_noi_suy(client, db_session):
    """Vẽ liền một đường qua chỗ không có dữ liệu là bịa ra đoạn không tồn tại."""
    user, headers, item = _setup(db_session, "mh.b@example.com")
    _answer(db_session, user, item, mastery=None, correct=True, minutes=0, source=None)
    _answer(db_session, user, item, mastery=0.6, correct=True, minutes=5)
    db_session.commit()

    body = client.get(f"/api/v1/progress/items/{item.id}/mastery-history",
                      headers=headers).json()
    assert [p["mastery"] for p in body["points"]] == [None, 0.6]
    assert body["answers_without_prediction"] == 1


def test_giu_lai_nguon_va_dang_bai_cua_tung_luot(client, db_session):
    """Cần để phân biệt điểm do DKT chấm với điểm rơi về prior."""
    user, headers, item = _setup(db_session, "mh.c@example.com")
    _answer(db_session, user, item, mastery=0.5, correct=True, minutes=0,
            source="prior", fmt="flashcard")
    _answer(db_session, user, item, mastery=0.7, correct=True, minutes=5,
            source="model", fmt="typing")
    db_session.commit()

    points = client.get(f"/api/v1/progress/items/{item.id}/mastery-history",
                        headers=headers).json()["points"]
    assert [p["source"] for p in points] == ["prior", "model"]
    assert [p["exercise_format"] for p in points] == ["flashcard", "typing"]


def test_chua_hoc_thi_duong_cong_rong_chu_khong_loi(client, db_session):
    _, headers, item = _setup(db_session, "mh.d@example.com")
    body = client.get(f"/api/v1/progress/items/{item.id}/mastery-history",
                      headers=headers).json()
    assert body["points"] == [] and body["total_answers"] == 0
    assert body["current_mastery"] is None


def test_khong_xem_duoc_tu_cua_nguoi_khac(client, db_session):
    _, _, item = _setup(db_session, "mh.e@example.com")
    _, other, _ = _setup(db_session, "mh.f@example.com")
    resp = client.get(f"/api/v1/progress/items/{item.id}/mastery-history", headers=other)
    assert resp.status_code == 404


def test_yeu_cau_dang_nhap(client, db_session):
    _, _, item = _setup(db_session, "mh.g@example.com")
    assert client.get(f"/api/v1/progress/items/{item.id}/mastery-history").status_code == 401
