from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.account import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import account_service
from app.services.auth_service import authenticate_user, register_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    user = register_user(db, data)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, data)
    access_token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=access_token, email_verified=user.is_email_verified)


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)) -> VerifyEmailResponse:
    """UC-03 bước 3 — đổi token trong liên kết lấy trạng thái đã xác thực."""
    return VerifyEmailResponse(**account_service.verify_email(db, data.token))


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """UC-03 luồng 1a — gửi lại email xác thực (có giới hạn số lần)."""
    account_service.resend_verification(db, current_user)
    return MessageResponse(message="Đã gửi lại email xác thực.")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """UC-06 bước 1–2. Luồng 1a: luôn trả cùng một câu để không lộ email nào có thật."""
    account_service.request_password_reset(db, data.email)
    return MessageResponse(
        message="Nếu email tồn tại trong hệ thống, chúng tôi đã gửi liên kết đặt lại mật khẩu."
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)) -> Response:
    """UC-06 bước 3–4 — đặt mật khẩu mới bằng token trong email."""
    account_service.reset_password(db, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
