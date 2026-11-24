"""UC-07 đổi mật khẩu · UC-09 cài đặt · UC-10 đặt mục tiêu học.

USER_SETTINGS tạo lazy: người dùng cũ chưa có bản ghi thì lần đọc đầu tiên sẽ
sinh ra với giá trị mặc định, không cần migration dữ liệu.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    ChangePasswordRequest,
    GoalsUpdate,
    SettingsResponse,
    SettingsUpdate,
)
from app.services import audit_service


def get_or_create_settings(db: Session, user: User) -> UserSettings:
    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings_row is None:
        settings_row = UserSettings(user_id=user.id)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
    return settings_row


def get_settings(db: Session, user: User) -> SettingsResponse:
    return SettingsResponse.model_validate(get_or_create_settings(db, user))


def update_settings(db: Session, user: User, data: SettingsUpdate) -> SettingsResponse:
    """UC-09 bước 2–3 — lưu tùy chọn giao diện/quyền riêng tư & áp dụng ngay."""
    settings_row = get_or_create_settings(db, user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)

    db.commit()
    db.refresh(settings_row)
    return SettingsResponse.model_validate(settings_row)


def update_goals(db: Session, user: User, data: GoalsUpdate) -> SettingsResponse:
    """UC-10 bước 2–3 — lưu mục tiêu học (khoảng an toàn đã chặn ở schema, E1)."""
    settings_row = get_or_create_settings(db, user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)

    db.commit()
    db.refresh(settings_row)
    return SettingsResponse.model_validate(settings_row)


def change_password(db: Session, user: User, data: ChangePasswordRequest) -> None:
    """UC-07 — đổi mật khẩu khi đang đăng nhập.

    E1: mật khẩu hiện tại sai -> 400. E2: mật khẩu mới trùng mật khẩu cũ -> 400.
    Token cũ vẫn còn hạn (JWT không có danh sách thu hồi) — ghi chú ở UC-07 bước 3.
    """
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không đúng",
        )
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải khác mật khẩu hiện tại",
        )

    user.password_hash = hash_password(data.new_password)
    audit_service.log(
        db, user, action="user.password_change", target_type="user",
        target_id=user.id, commit=False,
    )
    db.commit()
