"""UC-54 — bảng xếp hạng theo XP (toàn thời gian & tuần)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.session import StudySession
from app.models.user_progress import UserProgress
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _user(db_session, email, xp=0):
    """register_user đã tạo sẵn UserProgress — chỉ cần đặt lại XP."""
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    if xp:
        progress = db_session.execute(
            select(UserProgress).where(UserProgress.user_id == u.id)
        ).scalar_one()
        progress.xp = xp
        db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _completed_session(db_session, user_id, xp, days_ago):
    ended = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db_session.add(StudySession(
        user_id=user_id, status="completed", started_at=ended, ended_at=ended,
        item_count=10, correct_count=10, xp_earned=xp,
    ))
    db_session.commit()


def test_leaderboard_all_time_order_and_me(client, db_session):
    _user(db_session, "lb.a1@example.com", xp=500)
    _user(db_session, "lb.a2@example.com", xp=300)
    _, headers = _user(db_session, "lb.a3@example.com", xp=100)

    body = client.get("/api/v1/community/leaderboard", headers=headers).json()
    assert body["scope"] == "all"
    xps = [r["xp"] for r in body["items"]]
    assert xps == sorted(xps, reverse=True)

    me = next(r for r in body["items"] if r["is_me"])
    assert me["xp"] == 100 and me["rank"] == body["my_rank"]
    assert me["level"] == 2 and me["level_title"] == "Người mới"  # 100 XP -> level 2
    assert body["my_row"] is None  # đã nằm trong top


def test_leaderboard_week_uses_recent_sessions_only(client, db_session):
    """Phạm vi tuần chỉ cộng XP các phiên hoàn thành trong 7 ngày gần nhất."""
    old_user, _ = _user(db_session, "lb.b1@example.com", xp=1000)
    _completed_session(db_session, old_user.id, xp=1000, days_ago=30)

    new_user, headers = _user(db_session, "lb.b2@example.com", xp=50)
    _completed_session(db_session, new_user.id, xp=50, days_ago=1)

    week = client.get("/api/v1/community/leaderboard?scope=week", headers=headers).json()
    by_id = {r["user_id"]: r for r in week["items"]}
    assert by_id[new_user.id]["xp"] == 50
    assert by_id[old_user.id]["xp"] == 0          # phiên 30 ngày trước không tính
    assert by_id[old_user.id]["level"] == 11      # level vẫn theo XP tích lũy


def test_leaderboard_my_row_when_outside_top(client, db_session):
    """Người xem ngoài top vẫn thấy hạng của mình qua my_row."""
    for i in range(3):
        _user(db_session, f"lb.c{i}@example.com", xp=1000 - i)
    _, headers = _user(db_session, "lb.clast@example.com", xp=1)

    body = client.get("/api/v1/community/leaderboard?limit=2", headers=headers).json()
    assert len(body["items"]) == 2
    assert all(r["is_me"] is False for r in body["items"])
    assert body["my_row"] is not None
    assert body["my_row"]["is_me"] is True and body["my_row"]["rank"] == body["my_rank"]


def test_leaderboard_requires_auth(client):
    assert client.get("/api/v1/community/leaderboard").status_code == 401


def _set_streak(db_session, user_id, streak):
    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user_id)
    ).scalar_one()
    progress.streak_count = streak
    db_session.commit()


def test_leaderboard_kem_streak_hien_tai(client, db_session):
    """Trang chủ xếp hạng theo XP nhưng hiện cả chuỗi ngày học, nên API phải trả."""
    u1, _ = _user(db_session, "lb.s1@example.com", xp=500)
    _set_streak(db_session, u1.id, 12)
    _, headers = _user(db_session, "lb.s2@example.com", xp=100)

    rows = client.get("/api/v1/community/leaderboard", headers=headers).json()["items"]
    top = next(r for r in rows if r["user_id"] == u1.id)
    assert top["streak_count"] == 12
    # Người chưa học ngày nào vẫn phải có trường này, giá trị 0 — không phải None
    me = next(r for r in rows if r["is_me"])
    assert me["streak_count"] == 0


def test_streak_khong_doi_theo_scope(client, db_session):
    """Streak là giá trị HIỆN TẠI. Xếp hạng theo XP tuần mà hiện 'streak của
    tuần' thì phải định nghĩa streak trong cửa sổ 7 ngày — một khái niệm không
    tồn tại, và sẽ mâu thuẫn với con số streak người học thấy ở mọi nơi khác."""
    u, headers = _user(db_session, "lb.s3@example.com", xp=400)
    _set_streak(db_session, u.id, 9)
    _completed_session(db_session, u.id, xp=50, days_ago=1)

    all_time = client.get("/api/v1/community/leaderboard?scope=all", headers=headers).json()
    week = client.get("/api/v1/community/leaderboard?scope=week", headers=headers).json()

    def _mine(body):
        return next(r for r in body["items"] if r["is_me"])["streak_count"]

    assert _mine(all_time) == _mine(week) == 9
