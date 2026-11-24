from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import config_service


def register_user(db: Session, data: RegisterRequest) -> User:
    existing = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được sử dụng")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role="learner",
    )
    db.add(user)

    try:
        db.flush()
        db.add(UserProgress(user_id=user.id))
        db.add(UserSettings(user_id=user.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được sử dụng") from exc

    # UC-03 bước 1: xếp email xác thực vào hàng đợi ngay sau khi đăng ký
    from app.services import account_service

    account_service.send_verification_email(db, user)

    db.refresh(user)
    return user


def authenticate_user(db: Session, data: LoginRequest) -> User:
    user = db.execute(select(User).where(User.email == data.email)).scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng"
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa")

    # UC-04 E3 — chỉ chặn khi Admin bật "bắt buộc xác thực email" (UC-81)
    if not user.is_email_verified and config_service.get_bool("require_email_verification"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vui lòng xác thực email trước khi đăng nhập",
        )

    return user
