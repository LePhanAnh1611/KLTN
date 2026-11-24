"""UC-46 XP/level + UC-47 streak (mock DKT). Streak tính theo UTC (như service)."""
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from app.core.clock import DEFAULT_TIMEZONE, today_in
from app.core.security import create_access_token
from app.models.item import Item
from app.models.user_progress import UserProgress
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service, dkt_client
from app.services.auth_service import register_user
from app.services.gamification_service import compute_level, xp_per_correct


def _today():
    """Hôm nay theo MÚI GIỜ NGƯỜI HỌC (UC-88), không phải theo UTC.

    Với người học Việt (mặc định Asia/Ho_Chi_Minh) hai thứ này lệch nhau trong
    khoảng 00:00–07:00 giờ Việt — đúng khung giờ nhiều người học bài.
    """
    return today_in(ZoneInfo(DEFAULT_TIMEZONE))


def _setup(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"w{i}", meaning=f"m{i}") for i in range(3)]
    db_session.add_all(items)
    db_session.commit()
    for it in items:
        db_session.refresh(it)
    return user, headers, ws, items


def _study(client, headers, ws_id, items, results):
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws_id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    for it, ok in zip(items, results):
        client.post(f"/api/v1/sessions/{sid}/answer",
                    json={"item_id": it.id, "is_correct": ok}, headers=headers)
    return client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()


def test_compute_level():
    assert compute_level(0) == (1, 0, 100)
    assert compute_level(250) == (3, 50, 100)


def test_xp_awarded_on_complete(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "gm.a@example.com")
    summary = _study(client, headers, ws.id, items, [True, True, False])  # 2 đúng

    assert summary["xp_earned"] == 2 * xp_per_correct()
    prog = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    assert prog.xp == 2 * xp_per_correct()


def test_empty_session_no_xp(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, _ = _setup(db_session, "gm.b@example.com")
    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()
    assert summary["xp_earned"] == 0  # UC-30 E1


def test_streak_first_activity(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "gm.c@example.com")
    _study(client, headers, ws.id, items, [True])
    prog = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    assert prog.streak_count == 1
    assert prog.last_activity_date == _today()


def test_streak_continues_from_yesterday(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "gm.d@example.com")
    prog = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    prog.streak_count = 4
    prog.last_activity_date = _today() - timedelta(days=1)
    db_session.commit()

    _study(client, headers, ws.id, items, [True])
    db_session.refresh(prog)
    assert prog.streak_count == 5  # +1 liên tiếp


def test_streak_resets_after_gap(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "gm.e@example.com")
    prog = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    prog.streak_count = 9
    prog.last_activity_date = _today() - timedelta(days=3)  # đứt chuỗi
    db_session.commit()

    _study(client, headers, ws.id, items, [True])
    db_session.refresh(prog)
    assert prog.streak_count == 1  # reset


def test_dashboard_reflects_xp_after_study(client, db_session, monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.95 for x in t})
    _, headers, ws, items = _setup(db_session, "gm.f@example.com")
    _study(client, headers, ws.id, items, [True, True, True])  # 3 đúng -> 30 XP

    dash = client.get("/api/v1/dashboard", headers=headers).json()
    assert dash["xp"] == 30
    assert dash["streak_count"] == 1
    assert dash["items_mastered"] == 0  # mastery cao nhưng mới đúng một lần
    for _ in range(2):
        _study(client, headers, ws.id, items, [True, True, True])
    assert client.get("/api/v1/dashboard", headers=headers).json()["items_mastered"] == 3


def test_summary_reports_streak_only_on_first_session_of_day(client, db_session, monkeypatch):
    """UC-47 — chuỗi chỉ nhích lên ở phiên ĐẦU TIÊN trong ngày.

    Phiên thứ hai cùng ngày vẫn cho XP nhưng KHÔNG được báo "+1 chuỗi": báo ở
    mọi phiên thì con số mất ý nghĩa và người học hết tin vào nó.
    """
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, items = _setup(db_session, "gm.streak1@example.com")

    first = _study(client, headers, ws.id, items[:1], [True])
    assert first["streak_extended"] is True
    assert first["streak_count"] == 1

    # Phiên hai học TỪ KHÁC — nếu học lại đúng từ cũ thì BR-XP-01 không cấp XP
    # nữa, và test sẽ không còn kiểm được điều nó muốn kiểm.
    second = _study(client, headers, ws.id, items[1:2], [True])
    assert second["streak_extended"] is False
    assert second["streak_count"] == 1          # vẫn là chuỗi cũ, không cộng thêm
    assert second["xp_earned"] > 0              # nhưng XP thì vẫn có


def test_xp_chi_cap_mot_lan_moi_tu_moi_ngay(client, db_session, monkeypatch):
    """BR-XP-01 — chặn cày XP bằng cách trả lời lại từ cũ.

    Không có luật này thì bấm đúng cùng 4 từ mười vòng là +400 XP, mà XP nuôi
    cấp độ (UC-46) và bảng xếp hạng (UC-55).
    """
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, items = _setup(db_session, "gm.xpcap@example.com")
    unit = config_service.get_int("xp_per_correct")

    first = _study(client, headers, ws.id, items, [True, True, True])
    assert first["xp_earned"] == 3 * unit          # 3 từ mới -> có XP

    for _ in range(3):                              # cày lại đúng ba từ đó
        again = _study(client, headers, ws.id, items, [True, True, True])
        assert again["xp_earned"] == 0

    dash = client.get("/api/v1/dashboard", headers=headers).json()
    assert dash["xp"] == 3 * unit                   # tổng KHÔNG nhích thêm


def test_xp_van_cap_cho_tu_moi_trong_cung_ngay(client, db_session, monkeypatch):
    """Luật chặn cày KHÔNG được chặn nhầm việc học thêm từ mới trong ngày."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, items = _setup(db_session, "gm.xpnew@example.com")
    unit = config_service.get_int("xp_per_correct")

    assert _study(client, headers, ws.id, items[:1], [True])["xp_earned"] == unit
    # từ cũ + hai từ mới -> chỉ hai từ mới được tính
    assert _study(client, headers, ws.id, items, [True, True, True])["xp_earned"] == 2 * unit


def test_tra_loi_sai_roi_dung_lai_trong_ngay_van_duoc_xp(client, db_session, monkeypatch):
    """Sai rồi sửa được là học thật — lượt SAI không tiêu mất suất XP của từ."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, items = _setup(db_session, "gm.xpretry@example.com")
    unit = config_service.get_int("xp_per_correct")

    assert _study(client, headers, ws.id, items[:1], [False])["xp_earned"] == 0
    assert _study(client, headers, ws.id, items[:1], [True])["xp_earned"] == unit


def test_summary_streak_count_follows_the_chain(client, db_session, monkeypatch):
    """Số báo ra phải là chuỗi SAU khi cộng, không phải chuỗi trước đó."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    user, headers, ws, items = _setup(db_session, "gm.streak2@example.com")
    prog = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    prog.streak_count = 6
    prog.last_activity_date = _today() - timedelta(days=1)
    db_session.commit()

    summary = _study(client, headers, ws.id, items, [True])
    assert summary["streak_extended"] is True
    assert summary["streak_count"] == 7


def test_empty_session_reports_no_streak(client, db_session, monkeypatch):
    """Phiên không trả lời câu nào thì không cấp XP -> cũng không đụng tới chuỗi."""
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})
    _, headers, ws, _ = _setup(db_session, "gm.streak3@example.com")

    sid = client.post("/api/v1/sessions", json={"word_set_id": ws.id, "mode": "flashcard"},
                      headers=headers).json()["id"]
    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()

    assert summary["streak_extended"] is False
    assert summary["xp_earned"] == 0
