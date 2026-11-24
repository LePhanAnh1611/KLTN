"""UC-03 xác thực email · UC-06 quên/đặt lại mật khẩu.

Email đi qua đúng mắt xích UC-61/UC-62: chỉ xếp vào EMAIL_QUEUE, worker gửi sau.
Nhờ vậy hai luồng này chạy được cả khi backend gửi email đang ở chế độ 'log'.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.auth_token import PURPOSE_EMAIL_VERIFY, PURPOSE_PASSWORD_RESET, AuthToken
from app.models.post import Post
from app.models.post_comment import PostComment
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.account import ResetPasswordRequest
from app.schemas.account_delete import DeleteAccountRequest
from app.services import audit_service, email_service, token_service


def _link(path: str, token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/{path}?token={token}"


# --- UC-03 -------------------------------------------------------------------

def send_verification_email(db: Session, user: User, *, commit: bool = True) -> None:
    """Bước 1–2 — sinh token có hạn rồi xếp email vào hàng đợi."""
    token = token_service.issue(db, user, PURPOSE_EMAIL_VERIFY, commit=False)
    email_service.enqueue(
        db, user,
        to_email=user.email,
        subject="[LearningHub] Xác thực địa chỉ email",
        body=(
            f"Chào {user.display_name},\n\n"
            "Bấm vào liên kết dưới đây để xác thực email và kích hoạt đầy đủ tài khoản:\n"
            f"{_link('verify-email', token)}\n\n"
            "Liên kết có hạn 24 giờ. Nếu bạn không đăng ký tài khoản này, hãy bỏ qua email.\n"
        ),
        template="email_verify", commit=False,
    )
    if commit:
        db.commit()


def resend_verification(db: Session, user: User) -> None:
    """Luồng 1a — gửi lại, có giới hạn số lần trong một khoảng thời gian."""
    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email này đã được xác thực"
        )
    if token_service.recent_issue_count(db, user, PURPOSE_EMAIL_VERIFY) >= token_service.MAX_ISSUES_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã yêu cầu gửi lại quá nhiều lần, vui lòng thử lại sau",
        )
    send_verification_email(db, user)


def verify_email(db: Session, token: str) -> dict:
    """Bước 3 — đổi token lấy trạng thái đã xác thực.

    E1 token sai/hết hạn -> 400. E2 đã xác thực trước đó -> trả về bình thường
    kèm cờ `already_verified` để frontend điều hướng sang đăng nhập.
    """
    user = token_service.consume(db, token, PURPOSE_EMAIL_VERIFY)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Liên kết xác thực không hợp lệ hoặc đã hết hạn",
        )

    already = user.is_email_verified
    user.is_email_verified = True
    db.commit()
    return {"email": user.email, "already_verified": already}


# --- UC-06 -------------------------------------------------------------------

def request_password_reset(db: Session, email: str) -> None:
    """Bước 1–2. Luồng 1a: email không tồn tại vẫn im lặng thành công để không
    lộ tài khoản nào có thật."""
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not user.is_active:
        return
    if token_service.recent_issue_count(db, user, PURPOSE_PASSWORD_RESET) >= token_service.MAX_ISSUES_PER_WINDOW:
        return   # cũng im lặng: không tiết lộ đã gửi bao nhiêu lần

    token = token_service.issue(db, user, PURPOSE_PASSWORD_RESET, commit=False)
    email_service.enqueue(
        db, user,
        to_email=user.email,
        subject="[LearningHub] Đặt lại mật khẩu",
        body=(
            f"Chào {user.display_name},\n\n"
            "Bấm vào liên kết dưới đây để đặt lại mật khẩu:\n"
            f"{_link('reset-password', token)}\n\n"
            "Liên kết có hạn 1 giờ và chỉ dùng được một lần. "
            "Nếu bạn không yêu cầu đổi mật khẩu, hãy bỏ qua email này.\n"
        ),
        template="password_reset", commit=False,
    )
    db.commit()


def reset_password(db: Session, data: ResetPasswordRequest) -> None:
    """Bước 3–4 — kiểm token, đặt mật khẩu mới, vô hiệu token (E1 hết hạn -> 400).

    Token cũ hết hiệu lực ngay, nhưng JWT đã phát trước đó vẫn còn hạn — hệ thống
    không có danh sách thu hồi (ghi chú ở hậu điều kiện UC-06).
    """
    user = token_service.consume(db, data.token, PURPOSE_PASSWORD_RESET)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn",
        )

    user.password_hash = hash_password(data.new_password)
    audit_service.log(
        db, user, action="user.password_reset", target_type="user",
        target_id=user.id, commit=False,
    )
    db.commit()


def mark_verified_now(user: User) -> None:
    """Dùng khi seed/demo: bỏ qua bước bấm liên kết."""
    user.is_email_verified = True
    user.updated_at = datetime.now(timezone.utc)


def delete_account(db: Session, user: User, data: DeleteAccountRequest) -> None:
    """UC-12 — người học tự xóa tài khoản.

    XÓA MỀM theo Q6, không xóa cứng: INTERACTION của người này là dữ liệu huấn
    luyện DKT và là căn cứ cho mọi thống kê đã phát sinh; xóa cứng sẽ để lại
    khóa ngoại gãy khắp nơi.

    Những gì thực sự xảy ra:
    - `deleted_at` + `is_active=False` -> không đăng nhập lại được, và
      `get_current_user` từ chối token cũ ngay lập tức;
    - email/tên đổi thành chuỗi ẩn danh -> dữ liệu định danh biến mất khỏi hệ
      thống VÀ địa chỉ email được giải phóng cho lần đăng ký sau (cột email là
      UNIQUE, giữ nguyên thì người dùng không đăng ký lại được bằng email cũ);
    - avatar/bio xóa trắng; bộ từ riêng và bài viết xóa mềm để không còn hiện ra
      trong Khám phá / Bảng tin.

    E1: sai mật khẩu -> 400. E2: không xác nhận -> 400.
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần xác nhận trước khi xóa tài khoản",
        )
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu không đúng"
        )

    now = datetime.now(timezone.utc)

    audit_service.log(
        db, user, action="user.delete_account", target_type="user",
        target_id=user.id, detail=user.email, commit=False,
    )

    # Bộ từ riêng: xóa mềm (Q6) — Interaction trỏ tới item vẫn còn nguyên
    db.execute(
        update(WordSet)
        .where(WordSet.owner_id == user.id, WordSet.deleted_at.is_(None))
        .values(deleted_at=now, is_public=False)
    )
    # Bài viết & bình luận: gỡ khỏi bảng tin
    db.execute(
        update(Post).where(Post.author_id == user.id, Post.deleted_at.is_(None))
        .values(deleted_at=now)
    )
    db.execute(
        update(PostComment)
        .where(PostComment.author_id == user.id, PostComment.deleted_at.is_(None))
        .values(deleted_at=now)
    )
    # Token còn hạn (xác thực email / đặt lại mật khẩu) phải chết theo tài khoản
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))

    user.deleted_at = now
    user.is_active = False
    user.email = f"deleted+{user.id}@removed.invalid"
    user.display_name = "Người dùng đã xóa"
    user.avatar_url = None
    user.bio = None

    db.commit()
