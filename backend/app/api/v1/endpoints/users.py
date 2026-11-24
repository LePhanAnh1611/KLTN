from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.account_delete import DeleteAccountRequest
from app.schemas.auth import UserResponse
from app.schemas.settings import (
    ChangePasswordRequest,
    GoalsUpdate,
    SettingsResponse,
    SettingsUpdate,
)
from app.schemas.user import AvatarResponse, PublicProfile, UserUpdateRequest
from app.services import account_service, settings_service
from app.services.user_service import get_public_profile, update_avatar, update_profile

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = update_profile(db, current_user, data)
    return UserResponse.model_validate(user)


@router.post("/me/avatar", response_model=AvatarResponse)
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AvatarResponse:
    user = update_avatar(db, current_user, file)
    return AvatarResponse(avatar_url=user.avatar_url)


@router.get("/me/settings", response_model=SettingsResponse)
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """UC-09 + UC-10 — tùy chọn giao diện & mục tiêu học hiện tại."""
    return settings_service.get_settings(db, current_user)


@router.put("/me/settings", response_model=SettingsResponse)
def update_settings(
    data: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """UC-09 — dark mode, ngôn ngữ, giờ nhắc (UC-63), quyền riêng tư hồ sơ (UC-55)."""
    return settings_service.update_settings(db, current_user, data)


@router.put("/me/goals", response_model=SettingsResponse)
def update_goals(
    data: GoalsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """UC-10 — số từ/ngày, mục tiêu XP/ngày, mục tiêu CEFR."""
    return settings_service.update_goals(db, current_user, data)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-07 — đổi mật khẩu (E1 sai mật khẩu cũ, E2 trùng mật khẩu cũ)."""
    settings_service.change_password(db, current_user, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-12 — tự xóa tài khoản (xóa mềm theo Q6; E1 sai mật khẩu, E2 chưa xác nhận)."""
    account_service.delete_account(db, current_user, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{user_id}/public", response_model=PublicProfile)
def get_public_profile_of(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicProfile:
    """UC-55 — hồ sơ công khai của một người học (tôn trọng quyền riêng tư UC-09)."""
    return get_public_profile(db, current_user, user_id)
