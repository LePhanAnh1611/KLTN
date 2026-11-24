import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.schemas.achievement import AchievementStatus
from app.schemas.user import PublicProfile, UserUpdateRequest
from app.services.achievement_service import list_with_status
from app.services.gamification_service import compute_level, level_title
from app.services.mastery_service import mastered_item_ids

UPLOAD_DIR = Path("uploads/avatars")
MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def get_public_profile(db: Session, viewer: User, user_id: int) -> PublicProfile:
    """UC-55 — hồ sơ công khai: level, XP, streak, huy hiệu đã mở.

    E1: hồ sơ đặt riêng tư (UC-09 `profile_visibility='private'`) thì ẩn chỉ số,
    trừ khi người xem chính là chủ hồ sơ.
    """
    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng"
        )

    is_me = target.id == viewer.id
    visibility = db.execute(
        select(UserSettings.profile_visibility).where(UserSettings.user_id == target.id)
    ).scalar_one_or_none()
    hidden = visibility == "private" and not is_me

    profile = PublicProfile(
        user_id=target.id,
        display_name=target.display_name,
        avatar_url=target.avatar_url,
        is_private=hidden,
        is_me=is_me,
    )
    if hidden:
        return profile

    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == target.id)
    ).scalar_one_or_none()
    xp = progress.xp if progress else 0
    level, _, _ = compute_level(xp)

    profile.bio = target.bio
    profile.joined_at = target.created_at
    profile.level = level
    profile.level_title = level_title(level)
    profile.xp = xp
    profile.streak_count = progress.streak_count if progress else 0
    profile.items_mastered = len(mastered_item_ids(db, target.id))
    profile.achievements = [
        AchievementStatus(**a) for a in list_with_status(db, target) if a["unlocked"]
    ]
    return profile


def update_profile(db: Session, user: User, data: UserUpdateRequest) -> User:
    user.display_name = data.display_name
    user.bio = data.bio
    db.commit()
    db.refresh(user)
    return user


def update_avatar(db: Session, user: User, file: UploadFile) -> User:
    extension = ALLOWED_AVATAR_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Định dạng ảnh không hỗ trợ (chỉ nhận jpg/png/webp)",
        )

    contents = file.file.read()
    if len(contents) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ảnh vượt quá dung lượng cho phép (tối đa 2MB)",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}_{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / filename).write_bytes(contents)

    old_avatar_url = user.avatar_url
    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)

    if old_avatar_url:
        old_path = Path(old_avatar_url.lstrip("/"))
        if old_path.is_file():
            old_path.unlink(missing_ok=True)

    return user
