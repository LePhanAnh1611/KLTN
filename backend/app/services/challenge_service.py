"""UC-44 — Thử thách hôm nay.

Ba thử thách cố định mỗi ngày, tiến độ đọc thẳng từ dữ liệu đã có (INTERACTION,
SESSION) chứ không lưu bộ đếm riêng. Lý do: bộ đếm riêng là bản sao của sự thật,
và bản sao thì sẽ lệch — người học trả lời qua đường nào cũng phải được tính,
kể cả các luồng thêm sau này.

Thứ duy nhất cần lưu là "đã nhận thưởng chưa" (CHALLENGE_CLAIM), vì XP đã cấp
thì không suy ngược lại được từ INTERACTION.

Ngày tính theo UTC cho khớp với streak (UC-47) và mục tiêu ngày (UC-41) — ba chỗ
này phải cùng một định nghĩa "hôm nay", nếu không sẽ có ngày người học thấy
streak tăng mà thử thách lại chưa reset.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zoneinfo import ZoneInfo

from app.core.clock import user_today, user_zone
from app.models.challenge_claim import ChallengeClaim
from app.models.interaction import Interaction
from app.models.session import StudySession
from app.models.user import User
from app.schemas.challenge import ChallengeItem, DailyChallenges
from app.services import config_service, gamification_service


@dataclass(frozen=True)
class ChallengeDef:
    code: str
    title: str
    description: str
    config_key: str      # mục tiêu lấy từ cấu hình (UC-81), không hardcode
    xp_key: str


CHALLENGES: list[ChallengeDef] = [
    ChallengeDef(
        "answer_words", "Trả lời {target} từ",
        "Trả lời bất kỳ từ nào trong ngày, đúng hay sai đều tính.",
        "challenge_answer_target", "challenge_answer_xp",
    ),
    ChallengeDef(
        "correct_streak", "Trả lời đúng {target} từ",
        "Đếm số lượt trả lời ĐÚNG trong ngày.",
        "challenge_correct_target", "challenge_correct_xp",
    ),
    ChallengeDef(
        "finish_session", "Hoàn thành {target} phiên học",
        "Kết thúc phiên học (không tính phiên bỏ dở).",
        "challenge_session_target", "challenge_session_xp",
    ),
]
_BY_CODE = {c.code: c for c in CHALLENGES}


def today_for(db: Session, user: User) -> date_:
    """Ngày "hôm nay" theo múi giờ người học (UC-88).

    Tên cũ là `today_utc`: thử thách reset lúc 00:00 UTC, tức 07:00 sáng giờ
    Việt Nam — người học đêm hôm trước làm xong vẫn thấy thử thách cũ.
    """
    return user_today(db, user.id)


def _day_bounds(zone: ZoneInfo, day: date_) -> tuple[datetime, datetime]:
    """Mốc đầu/cuối của `day` theo múi giờ người học, quy về UTC để truy vấn.

    Dán thẳng `tzinfo=timezone.utc` như trước là sai 7 tiếng với người học Việt:
    thử thách reset lúc 07:00 sáng thay vì nửa đêm.
    """
    start = datetime.combine(day, time.min, tzinfo=zone)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def _progress(db: Session, user: User, day: date_) -> dict[str, int]:
    """Tiến độ hiện tại của cả ba thử thách, đọc từ dữ liệu gốc."""
    start, end = _day_bounds(user_zone(db, user.id), day)

    answered, correct = db.execute(
        select(
            func.count(),
            func.count().filter(Interaction.is_correct.is_(True)),
        ).where(
            Interaction.user_id == user.id,
            Interaction.answered_at >= start,
            Interaction.answered_at < end,
        )
    ).one()

    sessions = db.execute(
        select(func.count()).where(
            StudySession.user_id == user.id,
            StudySession.status == "completed",
            StudySession.ended_at >= start,
            StudySession.ended_at < end,
        )
    ).scalar_one()

    return {
        "answer_words": answered,
        "correct_streak": correct,
        "finish_session": sessions,
    }


def _claimed_codes(db: Session, user: User, day: date_) -> set[str]:
    return set(db.execute(
        select(ChallengeClaim.code).where(
            ChallengeClaim.user_id == user.id, ChallengeClaim.challenge_date == day
        )
    ).scalars().all())


def get_today(db: Session, user: User) -> DailyChallenges:
    """UC-44 — ba thử thách của hôm nay kèm tiến độ và trạng thái nhận thưởng."""
    day = today_for(db, user)
    progress = _progress(db, user, day)
    claimed = _claimed_codes(db, user, day)

    items: list[ChallengeItem] = []
    for definition in CHALLENGES:
        target = config_service.get_int(definition.config_key)
        current = min(progress[definition.code], target)
        items.append(ChallengeItem(
            code=definition.code,
            title=definition.title.format(target=target),
            description=definition.description,
            target=target,
            progress=current,
            completed=current >= target,
            claimed=definition.code in claimed,
            xp_reward=config_service.get_int(definition.xp_key),
        ))

    return DailyChallenges(
        date=day,
        items=items,
        claimable_count=sum(1 for i in items if i.completed and not i.claimed),
    )


def claim(db: Session, user: User, code: str) -> DailyChallenges:
    """Nhận thưởng một thử thách đã hoàn thành.

    E1: mã không tồn tại -> 404. E2: chưa đạt mục tiêu -> 400.
    E3: đã nhận rồi -> 409 (ràng buộc UNIQUE là chốt chặn cuối, kiểm ở đây để
    trả lỗi cho ra lỗi thay vì để vỡ ở tầng DB).
    """
    definition = _BY_CODE.get(code)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không có thử thách này"
        )

    day = today_for(db, user)
    if code in _claimed_codes(db, user, day):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bạn đã nhận thưởng thử thách này rồi"
        )

    target = config_service.get_int(definition.config_key)
    if _progress(db, user, day)[code] < target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn chưa hoàn thành thử thách này"
        )

    xp = config_service.get_int(definition.xp_key)
    db.add(ChallengeClaim(
        user_id=user.id, challenge_date=day, code=code, xp_awarded=xp,
    ))
    # Cấp XP qua gamification_service để lên cấp / mở huy hiệu vẫn chạy đúng
    gamification_service.award_xp(db, user, xp)
    db.commit()

    return get_today(db, user)
