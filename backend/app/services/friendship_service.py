"""UC-56 kết bạn/theo dõi · UC-57 chia sẻ tiến độ lên cộng đồng.

Quan hệ bạn bè lưu MỘT hàng cho mỗi cặp, nên mọi truy vấn "bạn của tôi" phải
nhìn cả `requester_id` lẫn `addressee_id`. Đổi lại không bao giờ có chuyện hai
hàng đối xứng lệch trạng thái nhau.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.friendship import Friendship
from app.models.user import User
from app.models.user_progress import UserProgress
from app.schemas.community import PostCard, PostCreate
from app.schemas.friendship import (
    FriendRequestRow,
    FriendRow,
    FriendshipState,
    UserSearchRow,
)
from app.services import community_service, notification_service
from app.services.gamification_service import compute_level, level_title
from app.services.mastery_service import mastered_item_ids


def _get_target(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None or not target.is_active or target.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng"
        )
    return target


def _pair(db: Session, a_id: int, b_id: int) -> Friendship | None:
    """Quan hệ giữa hai người, bất kể ai là người gửi."""
    return db.execute(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == a_id) & (Friendship.addressee_id == b_id),
                (Friendship.requester_id == b_id) & (Friendship.addressee_id == a_id),
            )
        )
    ).scalars().first()


def get_state(db: Session, user: User, other_id: int) -> FriendshipState:
    """Trạng thái quan hệ nhìn từ phía `user` — để nút trên hồ sơ hiện đúng chữ."""
    if other_id == user.id:
        return FriendshipState(status="self", friendship_id=None, is_incoming=False)

    row = _pair(db, user.id, other_id)
    if row is None or row.status == "declined":
        # Đã từ chối thì cho phép gửi lại — quan hệ không nên bị khóa vĩnh viễn
        return FriendshipState(status="none", friendship_id=None, is_incoming=False)

    return FriendshipState(
        status=row.status,
        friendship_id=row.id,
        is_incoming=(row.status == "pending" and row.addressee_id == user.id),
    )


def send_request(db: Session, user: User, target_id: int) -> FriendshipState:
    """E1: tự kết bạn với mình -> 400. E2: đã có quan hệ đang mở -> 409."""
    if target_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể tự kết bạn với chính mình"
        )
    target = _get_target(db, target_id)

    existing = _pair(db, user.id, target_id)
    if existing is not None and existing.status in ("pending", "accepted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Đã là bạn bè hoặc đang có lời mời chờ trả lời",
        )

    if existing is not None:
        # Tái sử dụng hàng cũ đã bị từ chối: ràng buộc UNIQUE trên cặp không cho
        # thêm hàng mới, và giữ một hàng cũng đúng với mô hình "một cặp một hàng".
        existing.requester_id = user.id
        existing.addressee_id = target_id
        existing.status = "pending"
        existing.responded_at = None
        friendship = existing
    else:
        friendship = Friendship(requester_id=user.id, addressee_id=target_id, status="pending")
        db.add(friendship)

    notification_service.notify(
        db, target.id, type_="community",
        title="Lời mời kết bạn",
        body=f"{user.display_name} muốn kết bạn với bạn.",
        link=f"/users/{user.id}", commit=False,
    )
    db.commit()
    db.refresh(friendship)
    return get_state(db, user, target_id)


def _get_pending_for_me(db: Session, user: User, friendship_id: int) -> Friendship:
    row = db.get(Friendship, friendship_id)
    if row is None or row.addressee_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lời mời"
        )
    if row.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Lời mời này đã được trả lời"
        )
    return row


def respond(db: Session, user: User, friendship_id: int, accept: bool) -> FriendshipState:
    """Chỉ NGƯỜI NHẬN mới trả lời được lời mời (E1: không phải của mình -> 404)."""
    row = _get_pending_for_me(db, user, friendship_id)
    row.status = "accepted" if accept else "declined"
    row.responded_at = datetime.now(timezone.utc)

    if accept:
        notification_service.notify(
            db, row.requester_id, type_="community",
            title="Lời mời được chấp nhận",
            body=f"{user.display_name} đã đồng ý kết bạn.",
            link=f"/users/{user.id}", commit=False,
        )
    db.commit()
    return get_state(db, user, row.requester_id)


def unfriend(db: Session, user: User, other_id: int) -> None:
    """Hủy kết bạn hoặc rút lại lời mời đã gửi. Xóa hẳn hàng để hai người có thể
    kết bạn lại từ đầu — quan hệ xã hội không cần lịch sử ở phạm vi khóa luận."""
    row = _pair(db, user.id, other_id)
    if row is not None:
        db.delete(row)
        db.commit()


def list_friends(db: Session, user: User) -> list[FriendRow]:
    rows = db.execute(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        )
    ).scalars().all()

    friend_ids = [
        r.addressee_id if r.requester_id == user.id else r.requester_id for r in rows
    ]
    return _rows_for(db, friend_ids)


def _rows_for(db: Session, user_ids: list[int]) -> list[FriendRow]:
    """Thông tin hiển thị của một nhóm người dùng (bỏ tài khoản đã xóa)."""
    if not user_ids:
        return []
    people = db.execute(
        select(User, UserProgress)
        .outerjoin(UserProgress, UserProgress.user_id == User.id)
        .where(User.id.in_(user_ids), User.deleted_at.is_(None))
    ).all()

    out: list[FriendRow] = []
    for person, progress in people:
        xp = progress.xp if progress else 0
        level, _, _ = compute_level(xp)
        out.append(FriendRow(
            user_id=person.id, display_name=person.display_name,
            avatar_url=person.avatar_url, level=level, level_title=level_title(level),
            xp=xp, streak_count=progress.streak_count if progress else 0,
        ))
    return sorted(out, key=lambda r: r.xp, reverse=True)


SEARCH_LIMIT = 20
SEARCH_MIN_NAME_LEN = 2


def search_users(db: Session, user: User, q: str) -> list[UserSearchRow]:
    """Tìm người để kết bạn theo ID hoặc tên hiển thị.

    - `q` toàn chữ số (cho phép tiền tố `#`, như "#12") -> khớp ĐÚNG ID.
    - Ngược lại -> tên chứa `q`, không phân biệt hoa thường; cần ≥ 2 ký tự để
      không trả về cả bảng người dùng khi gõ 1 chữ.
    Bỏ chính mình, tài khoản đã xóa / bị khóa.
    """
    term = q.strip()
    id_term = term.lstrip("#").strip()
    stmt = select(User).where(
        User.id != user.id, User.is_active.is_(True), User.deleted_at.is_(None),
    )
    if id_term.isdigit():
        stmt = stmt.where(User.id == int(id_term))
    else:
        if len(term) < SEARCH_MIN_NAME_LEN:
            return []
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(User.display_name.ilike(f"%{escaped}%", escape="\\"))
    people = db.execute(stmt.order_by(User.display_name, User.id).limit(SEARCH_LIMIT)).scalars().all()
    return [
        UserSearchRow(
            user_id=p.id, display_name=p.display_name, avatar_url=p.avatar_url,
            friendship=get_state(db, user, p.id),
        )
        for p in people
    ]


def list_incoming_requests(db: Session, user: User) -> list[FriendRequestRow]:
    """Lời mời người khác gửi cho tôi, đang chờ trả lời."""
    rows = db.execute(
        select(Friendship, User)
        .join(User, User.id == Friendship.requester_id)
        .where(
            Friendship.addressee_id == user.id,
            Friendship.status == "pending",
            User.deleted_at.is_(None),
        )
        .order_by(Friendship.created_at.desc())
    ).all()
    return [
        FriendRequestRow(
            friendship_id=f.id, user_id=u.id, display_name=u.display_name,
            avatar_url=u.avatar_url, created_at=f.created_at,
        )
        for f, u in rows
    ]


def share_progress(db: Session, user: User, message: str | None) -> PostCard:
    """UC-57 — đăng một bài "khoe tiến độ" lên bảng tin.

    Chốt số liệu vào NỘI DUNG bài viết chứ không tham chiếu động: bài đăng là
    một mốc thời gian, đọc lại sau vài tháng phải thấy đúng con số lúc đăng,
    không phải con số hiện tại.
    """
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one_or_none()
    xp = progress.xp if progress else 0
    level, _, _ = compute_level(xp)

    lines = [
        f"🎯 Cấp {level} · {level_title(level)}",
        f"⭐ {xp} XP · 🔥 chuỗi {progress.streak_count if progress else 0} ngày",
        f"📚 Đã thuộc {len(mastered_item_ids(db, user.id))} từ",
    ]
    if message and message.strip():
        lines.insert(0, message.strip())

    return community_service.create_post(
        db, user, PostCreate(post_type="progress", content="\n".join(lines)),
    )
