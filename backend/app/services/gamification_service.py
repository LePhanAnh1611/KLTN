"""UC-46 XP/level + UC-47 streak — bộ luật hệ thống (M5).

Cấp XP & cập nhật streak khi hoàn thành phiên học (UC-30 gọi tới). Ngưỡng tạm
-> UC-81 cấu hình. items_mastered đồng bộ theo KNOWLEDGE_STATE (BR-01).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import user_day_bounds, user_today
from app.models.challenge_claim import ChallengeClaim
from app.models.interaction import Interaction
from app.models.session import StudySession
from app.models.user import User
from app.models.user_progress import UserProgress
from app.services import config_service
from app.services.mastery_service import mastered_item_ids


def xp_per_correct() -> int:
    """Q5: XP mỗi câu đúng (Admin chỉnh ở UC-81)."""
    return config_service.get_int("xp_per_correct")


def xp_per_level() -> int:
    """XP cần cho mỗi cấp (UC-81)."""
    return config_service.get_int("xp_per_level")


def default_daily_xp_goal() -> int:
    """UC-41: định mức mặc định khi người học chưa tự đặt (UC-81)."""
    return config_service.get_int("default_daily_xp_goal")


def default_daily_item_goal() -> int:
    """UC-10 luồng 1a: số từ/ngày mặc định khi người học chưa đặt (UC-81)."""
    return config_service.get_int("default_daily_item_goal")


def day_bounds(db: Session, user: User, moment: datetime | None = None) -> tuple[datetime, datetime]:
    """Mốc đầu và cuối của "hôm nay" THEO MÚI GIỜ NGƯỜI HỌC (UC-88).

    Gom về một chỗ vì streak (UC-47), mục tiêu ngày (UC-41), thử thách ngày
    (UC-44) và trần XP (BR-XP-01) đều phải hiểu "hôm nay" GIỐNG NHAU. Rải
    `now().date()` khắp nơi thì sửa múi giờ phải sửa từng chỗ, sót một chỗ là
    lệch số mà không ai thấy.
    """
    return user_day_bounds(db, user.id, moment)


def xp_eligible_item_count(db: Session, user: User, session: StudySession) -> int:
    """Số TỪ trong phiên thực sự được cấp XP.

    **BR-XP-01: mỗi từ chỉ cấp XP một lần mỗi ngày.**

    Không có luật này thì XP cày được vô hạn: trả lời đúng cùng 4 từ mười vòng
    là +400 XP, mà XP nuôi cấp độ (UC-46), bảng xếp hạng (UC-55) và mục tiêu
    ngày (UC-41) — tức là bảng xếp hạng mất hết ý nghĩa.

    Ôn lại từ cũ vẫn được khuyến khích: nó vẫn ghi Interaction, vẫn cập nhật
    mastery, vẫn tính vào thử thách "trả lời N từ". Chỉ riêng XP là không cộng
    thêm, vì XP đo *độ phủ việc học trong ngày* chứ không đo số lần bấm.
    """
    day_start, day_end = day_bounds(db, user, session.ended_at)

    correct_now = set(db.execute(
        select(Interaction.item_id).where(
            Interaction.session_id == session.id,
            Interaction.is_correct.is_(True),
        ).distinct()
    ).scalars().all())
    if not correct_now:
        return 0

    already = set(db.execute(
        select(Interaction.item_id).join(StudySession, StudySession.id == Interaction.session_id).where(
            Interaction.user_id == user.id,
            Interaction.is_correct.is_(True),
            Interaction.item_id.in_(correct_now),
            StudySession.id != session.id,
            StudySession.status == "completed",
            StudySession.ended_at >= day_start,
            StudySession.ended_at < day_end,
        ).distinct()
    ).scalars().all())

    return len(correct_now - already)


def today_xp(db: Session, user: User) -> int:
    """UC-41: tổng XP tích trong ngày hôm nay (UTC).

    Gồm XP từ phiên đã hoàn thành VÀ thưởng thử thách ngày (UC-44) — nếu chỉ
    đếm phiên thì người học nhận thưởng xong thấy tổng XP tăng mà vòng "mục tiêu
    hôm nay" đứng yên.
    """
    day_start, day_end = day_bounds(db, user)
    today = user_today(db, user.id)
    from_sessions = db.execute(
        select(func.coalesce(func.sum(StudySession.xp_earned), 0))
        .where(
            StudySession.user_id == user.id,
            StudySession.status == "completed",
            StudySession.ended_at >= day_start,
            StudySession.ended_at < day_end,
        )
    ).scalar_one()
    from_challenges = db.execute(
        select(func.coalesce(func.sum(ChallengeClaim.xp_awarded), 0))
        .where(
            ChallengeClaim.user_id == user.id,
            ChallengeClaim.challenge_date == today,
        )
    ).scalar_one()
    return int(from_sessions) + int(from_challenges)


def award_xp(db: Session, user: User, xp: int) -> int:
    """Cộng XP ngoài phiên học (VD thưởng thử thách UC-44) và cập nhật streak.

    Không commit: để caller gộp vào cùng transaction với việc ghi nhận lý do cấp
    XP, tránh trường hợp cấp XP xong mà bản ghi lý do lại rollback.
    """
    db.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if progress is None:
        progress = UserProgress(user_id=user.id)
        db.add(progress)
        db.flush()

    progress.xp += xp
    _update_streak(progress, user_today(db, user.id))
    db.flush()
    return progress.xp


def compute_level(xp: int) -> tuple[int, int, int]:
    """(level, xp_đã_tích_trong_level, xp_cho_level) từ tổng XP."""
    per_level = xp_per_level()
    return xp // per_level + 1, xp % per_level, per_level


def level_title(level: int) -> str:
    """UC-42: tên bậc theo cấp độ."""
    if level >= 10:
        return "Bậc thầy"
    if level >= 7:
        return "Giỏi"
    if level >= 5:
        return "Chăm chỉ"
    if level >= 3:
        return "Học viên"
    return "Người mới"


def _update_streak(progress: UserProgress, today: date) -> bool:
    """UC-47: duy trì/khôi phục streak theo ngày hoạt động gần nhất.

    Trả True nếu ĐÂY LÀ phiên đầu tiên trong ngày, tức là chuỗi vừa nhích lên.
    Người học cần được báo đúng lúc đó — báo ở mọi phiên thì con số mất ý nghĩa,
    mà không báo thì thành tích lớn nhất của ngày trôi qua lặng lẽ.
    """
    last = progress.last_activity_date
    if last == today:
        return False                  # đã tính hôm nay
    if last == today - timedelta(days=1):
        progress.streak_count += 1    # liên tiếp
    else:
        progress.streak_count = 1     # lần đầu hoặc đứt chuỗi
    progress.last_activity_date = today
    return True


@dataclass
class SessionAward:
    """Kết quả tính thưởng của một phiên."""

    xp_earned: int
    streak_count: int
    #: True khi phiên này là phiên ĐẦU TIÊN trong ngày -> chuỗi vừa +1
    streak_extended: bool


def award_session(db: Session, user: User, session: StudySession, *, commit: bool = True) -> SessionAward:
    """Cấp XP + cập nhật streak + đồng bộ items_mastered khi kết thúc phiên.
    (UC-30 E1: phiên rỗng -> caller không gọi hàm này.)"""
    # Serialize rewards for this learner, including simultaneous sessions.
    db.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if progress is None:  # phòng hờ — đăng ký đã tạo sẵn
        progress = UserProgress(user_id=user.id)
        db.add(progress)
        db.flush()

    # BR-XP-01: đếm số TỪ lần đầu đúng trong ngày, không đếm số lượt bấm đúng.
    xp_earned = xp_eligible_item_count(db, user, session) * xp_per_correct()
    progress.xp += xp_earned
    streak_extended = _update_streak(progress, user_today(db, user.id, session.ended_at))

    progress.items_mastered = len(mastered_item_ids(db, user.id))

    session.xp_earned = xp_earned
    if commit:
        db.commit()
    else:
        db.flush()
    return SessionAward(
        xp_earned=xp_earned,
        streak_count=progress.streak_count,
        streak_extended=streak_extended,
    )
