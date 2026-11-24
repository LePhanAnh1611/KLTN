"""UC-54 — Bảng xếp hạng người học theo XP.

Hai phạm vi: toàn thời gian (USER_PROGRESS.xp) và tuần (cộng xp_earned của các
phiên đã hoàn thành trong 7 ngày gần nhất — không cần bảng XP_LEDGER riêng).
Luôn kèm hạng của chính người xem, kể cả khi họ nằm ngoài top.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.session import StudySession
from app.models.user import User
from app.models.user_progress import UserProgress
from app.schemas.community import LeaderboardResponse, LeaderboardRow, LeaderboardScope
from app.services.gamification_service import compute_level, level_title

TOP_LIMIT = 20
WEEK_DAYS = 7


def _progress_map(db: Session) -> dict[int, tuple[int, int]]:
    """{user_id: (XP toàn thời gian, streak hiện tại)}.

    Level luôn tính từ XP tích lũy kể cả khi xếp hạng theo tuần, và streak luôn
    là giá trị hiện tại — một truy vấn lấy cả hai thay vì hai lượt quét bảng.
    """
    rows = db.execute(
        select(UserProgress.user_id, UserProgress.xp, UserProgress.streak_count)
    ).all()
    return {uid: (int(xp or 0), int(streak or 0)) for uid, xp, streak in rows}


def _ranked_all_time(db: Session) -> list[tuple[User, int]]:
    rows = db.execute(
        select(User, func.coalesce(UserProgress.xp, 0).label("xp"))
        .outerjoin(UserProgress, UserProgress.user_id == User.id)
        .where(User.is_active.is_(True))
        .order_by(func.coalesce(UserProgress.xp, 0).desc(), User.id)
    ).all()
    return [(user, int(xp)) for user, xp in rows]


def _ranked_week(db: Session) -> list[tuple[User, int]]:
    since = datetime.now(timezone.utc) - timedelta(days=WEEK_DAYS)
    week_xp = (
        select(
            StudySession.user_id.label("user_id"),
            func.coalesce(func.sum(StudySession.xp_earned), 0).label("xp"),
        )
        .where(StudySession.status == "completed", StudySession.ended_at >= since)
        .group_by(StudySession.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User, func.coalesce(week_xp.c.xp, 0).label("xp"))
        .outerjoin(week_xp, week_xp.c.user_id == User.id)
        .where(User.is_active.is_(True))
        .order_by(func.coalesce(week_xp.c.xp, 0).desc(), User.id)
    ).all()
    return [(user, int(xp)) for user, xp in rows]


def get_leaderboard(
    db: Session, user: User, *, scope: LeaderboardScope = "all", limit: int = TOP_LIMIT
) -> LeaderboardResponse:
    """Top người học theo XP + dòng của chính người xem (nếu nằm ngoài top)."""
    ranked = _ranked_week(db) if scope == "week" else _ranked_all_time(db)
    progress = _progress_map(db)

    def _row(rank: int, u: User, xp: int) -> LeaderboardRow:
        total_xp, streak = progress.get(u.id, (0, 0))
        level, _, _ = compute_level(total_xp)
        return LeaderboardRow(
            rank=rank, user_id=u.id, display_name=u.display_name,
            avatar_url=u.avatar_url, xp=xp, level=level,
            level_title=level_title(level), streak_count=streak,
            is_me=u.id == user.id,
        )

    top = [_row(i + 1, u, xp) for i, (u, xp) in enumerate(ranked[:limit])]

    my_rank = next((i + 1 for i, (u, _) in enumerate(ranked) if u.id == user.id), None)
    my_row = None
    if my_rank is not None and my_rank > limit:
        me, my_xp = ranked[my_rank - 1]
        my_row = _row(my_rank, me, my_xp)

    return LeaderboardResponse(scope=scope, items=top, my_rank=my_rank, my_row=my_row)
