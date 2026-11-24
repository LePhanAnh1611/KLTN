"""UC-56 kết bạn · UC-57 chia sẻ tiến độ."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.community import PostCard
from app.schemas.friendship import (
    FriendRequestRow,
    FriendRow,
    FriendshipState,
    ShareProgressRequest,
    UserSearchRow,
)
from app.services import friendship_service

router = APIRouter()


@router.get("/friends", response_model=list[FriendRow])
def list_friends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FriendRow]:
    """UC-56 — danh sách bạn bè, xếp theo XP."""
    return friendship_service.list_friends(db, current_user)


@router.get("/friends/search", response_model=list[UserSearchRow])
def search_users(
    q: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserSearchRow]:
    """UC-56 — tìm người để kết bạn theo tên hoặc ID (kèm trạng thái quan hệ)."""
    return friendship_service.search_users(db, current_user, q)


@router.get("/friends/requests", response_model=list[FriendRequestRow])
def list_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FriendRequestRow]:
    """UC-56 — lời mời đang chờ tôi trả lời."""
    return friendship_service.list_incoming_requests(db, current_user)


@router.get("/friends/state/{user_id}", response_model=FriendshipState)
def get_state(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendshipState:
    """UC-56 — quan hệ giữa tôi và người này (để nút trên hồ sơ hiện đúng chữ)."""
    return friendship_service.get_state(db, current_user, user_id)


@router.post("/friends/{user_id}", response_model=FriendshipState,
             status_code=status.HTTP_201_CREATED)
def send_request(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendshipState:
    """UC-56 — gửi lời mời (E1 tự kết bạn 400, E2 đã có quan hệ 409)."""
    return friendship_service.send_request(db, current_user, user_id)


@router.post("/friends/requests/{friendship_id}/accept", response_model=FriendshipState)
def accept(
    friendship_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendshipState:
    """UC-56 — đồng ý kết bạn."""
    return friendship_service.respond(db, current_user, friendship_id, accept=True)


@router.post("/friends/requests/{friendship_id}/decline", response_model=FriendshipState)
def decline(
    friendship_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendshipState:
    """UC-56 — từ chối (vẫn có thể kết bạn lại sau)."""
    return friendship_service.respond(db, current_user, friendship_id, accept=False)


@router.delete("/friends/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfriend(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-56 — hủy kết bạn hoặc rút lại lời mời đã gửi."""
    friendship_service.unfriend(db, current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/share-progress", response_model=PostCard, status_code=status.HTTP_201_CREATED)
def share_progress(
    data: ShareProgressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostCard:
    """UC-57 — đăng bài khoe tiến độ (số liệu chốt vào nội dung bài)."""
    return friendship_service.share_progress(db, current_user, data.message)
