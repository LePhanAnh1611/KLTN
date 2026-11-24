"""UC-48 mở khóa huy hiệu · UC-43 xem huy hiệu · UC-79 CRUD định nghĩa huy hiệu.

Định nghĩa huy hiệu nằm ở bảng ACHIEVEMENTS (Admin sửa được, UC-79) thay vì code.
Điều kiện đạt mô tả bằng dữ liệu: `stats[condition_key] >= threshold`, với stats
là chỉ số học tập của người dùng (XP / streak / từ đã thuộc / số phiên hoàn thành).
Sau mỗi phiên học, hệ thống đối chiếu và cấp huy hiệu mới.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.achievement import Achievement
from app.models.session import StudySession
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_progress import UserProgress
from app.services import notification_service
from app.services.mastery_service import mastered_item_ids

# Các chỉ số dùng được làm điều kiện (khớp khóa của `_stats`)
CONDITION_KEYS = ("sessions_completed", "xp", "streak", "mastered")

# Bộ huy hiệu mặc định — migration seed sẵn; hàm `ensure_seeded` dựng lại khi
# bảng còn trống (VD schema tạo bằng create_all trong test).
DEFAULT_ACHIEVEMENTS = [
    ("first_session", "Bước đầu tiên", "Hoàn thành phiên học đầu tiên", "sessions_completed", 1, 1),
    ("xp_100", "Tân binh", "Đạt 100 XP", "xp", 100, 2),
    ("xp_500", "Chăm chỉ", "Đạt 500 XP", "xp", 500, 3),
    ("streak_3", "Kiên trì", "Streak 3 ngày", "streak", 3, 4),
    ("streak_7", "Bền bỉ", "Streak 7 ngày", "streak", 7, 5),
    ("mastered_10", "Vốn từ vững", "Thuộc 10 từ", "mastered", 10, 6),
    ("mastered_50", "Bậc thầy từ vựng", "Thuộc 50 từ", "mastered", 50, 7),
]


def ensure_seeded(db: Session, *, commit: bool = True) -> None:
    """Nạp bộ huy hiệu mặc định nếu bảng còn trống."""
    if db.execute(select(func.count()).select_from(Achievement)).scalar_one():
        return
    db.add_all([
        Achievement(
            code=code, name=name, description=description,
            condition_key=condition_key, threshold=threshold, sort_order=sort_order,
        )
        for code, name, description, condition_key, threshold, sort_order in DEFAULT_ACHIEVEMENTS
    ])
    if commit:
        db.commit()
    else:
        db.flush()


def _definitions(db: Session, *, only_active: bool = True, commit: bool = True) -> list[Achievement]:
    ensure_seeded(db, commit=commit)
    query = select(Achievement)
    if only_active:
        query = query.where(Achievement.is_active.is_(True))
    return list(db.execute(query.order_by(Achievement.sort_order, Achievement.id)).scalars().all())


def _stats(db: Session, user: User) -> dict:
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one_or_none()
    sessions_completed = db.execute(
        select(func.count())
        .select_from(StudySession)
        .where(StudySession.user_id == user.id, StudySession.status == "completed")
    ).scalar_one()
    return {
        "xp": progress.xp if progress else 0,
        "streak": progress.streak_count if progress else 0,
        "mastered": len(mastered_item_ids(db, user.id)),
        "sessions_completed": sessions_completed,
    }


def check_and_unlock(db: Session, user: User, *, commit: bool = True) -> list[str]:
    """Cấp huy hiệu mới đủ điều kiện. Trả danh sách TÊN huy hiệu vừa mở."""
    unlocked_codes = set(db.execute(
        select(UserAchievement.achievement_code).where(UserAchievement.user_id == user.id)
    ).scalars().all())
    stats = _stats(db, user)
    newly: list[str] = []

    for a in _definitions(db, commit=commit):
        reached = stats.get(a.condition_key, 0) >= a.threshold
        if a.code not in unlocked_codes and reached:
            db.add(UserAchievement(user_id=user.id, achievement_code=a.code,
                                   unlocked_at=datetime.now(timezone.utc)))
            newly.append(a.name)
            # UC-61: sinh thông báo in-app cho huy hiệu vừa mở
            notification_service.notify(
                db, user.id, type_="achievement",
                title=f"Mở khóa huy hiệu: {a.name}",
                body=a.description, link="/achievements", commit=False,
            )
    if newly and commit:
        db.commit()
    elif newly:
        db.flush()
    return newly


def list_with_status(db: Session, user: User) -> list[dict]:
    """UC-43: mọi huy hiệu đang bật + trạng thái mở khóa (kèm thời điểm)."""
    rows = {
        code: at for code, at in db.execute(
            select(UserAchievement.achievement_code, UserAchievement.unlocked_at)
            .where(UserAchievement.user_id == user.id)
        ).all()
    }
    return [
        {
            "code": a.code, "name": a.name, "description": a.description,
            "unlocked": a.code in rows,
            "unlocked_at": rows.get(a.code),
        }
        for a in _definitions(db)
    ]


# --- UC-79 CRUD định nghĩa (Admin) -------------------------------------------

def list_definitions(db: Session) -> list[Achievement]:
    """UC-79 — mọi định nghĩa, kể cả huy hiệu đang tắt."""
    return _definitions(db, only_active=False)


def _validate_condition(condition_key: str) -> None:
    if condition_key not in CONDITION_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Điều kiện phải thuộc: {', '.join(CONDITION_KEYS)}",
        )


def create_definition(db: Session, data) -> Achievement:
    """UC-79 — thêm huy hiệu mới."""
    ensure_seeded(db)
    _validate_condition(data.condition_key)

    exists = db.execute(
        select(Achievement.id).where(Achievement.code == data.code)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Mã huy hiệu đã tồn tại"
        )

    achievement = Achievement(
        code=data.code, name=data.name, description=data.description,
        condition_key=data.condition_key, threshold=data.threshold,
        icon=data.icon, is_active=data.is_active, sort_order=data.sort_order,
    )
    db.add(achievement)
    db.commit()
    db.refresh(achievement)
    return achievement


def get_definition(db: Session, achievement_id: int) -> Achievement:
    achievement = db.get(Achievement, achievement_id)
    if achievement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy huy hiệu"
        )
    return achievement


def update_definition(db: Session, achievement_id: int, data) -> Achievement:
    """UC-79 — sửa tên/mô tả/điều kiện/trạng thái. `code` giữ nguyên vì
    USER_ACHIEVEMENTS tham chiếu tới nó."""
    achievement = get_definition(db, achievement_id)
    if data.condition_key is not None:
        _validate_condition(data.condition_key)
        achievement.condition_key = data.condition_key
    for field in ("name", "description", "threshold", "icon", "is_active", "sort_order"):
        value = getattr(data, field)
        if value is not None:
            setattr(achievement, field, value)

    db.commit()
    db.refresh(achievement)
    return achievement


def delete_definition(db: Session, achievement_id: int) -> None:
    """UC-79 — xóa định nghĩa. Huy hiệu ĐÃ CẤP cho người dùng vẫn giữ trong
    USER_ACHIEVEMENTS (không xóa lịch sử); nếu chỉ muốn ẩn thì đặt is_active=false."""
    achievement = get_definition(db, achievement_id)
    db.delete(achievement)
    db.commit()
