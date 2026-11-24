"""UC-49 đăng bài · UC-50 bình luận · UC-51 thích · UC-52 xóa bài.

Q3 (duyệt trước hiển thị): bài mang trạng thái theo `settings.require_post_approval`
— hiện tắt nên vào thẳng 'approved'; bật khi có trang kiểm duyệt UC-77 (M7).
Q6: xóa bài/bình luận là xóa mềm.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.post_comment import PostComment
from app.models.post_reaction import PostReaction
from app.models.user import User
from app.schemas.community import (
    CommentCreate,
    CommentResponse,
    PostCard,
    PostCreate,
    PostListResponse,
    ReactionResponse,
)
from app.services import config_service, notification_service

STATUS_APPROVED = "approved"
STATUS_PENDING = "pending"

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


def get_visible_post(db: Session, post_id: int) -> Post:
    """Bài còn hiển thị (chưa xóa mềm, đã duyệt); 404 nếu không."""
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None or post.status != STATUS_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bài viết không còn khả dụng"
        )
    return post


def _like_counts(db: Session, post_ids: list[int]) -> dict[int, int]:
    if not post_ids:
        return {}
    rows = db.execute(
        select(PostReaction.post_id, func.count(PostReaction.id))
        .where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id)
    ).all()
    return {pid: count for pid, count in rows}


def _comment_counts(db: Session, post_ids: list[int]) -> dict[int, int]:
    if not post_ids:
        return {}
    rows = db.execute(
        select(PostComment.post_id, func.count(PostComment.id))
        .where(PostComment.post_id.in_(post_ids), PostComment.deleted_at.is_(None))
        .group_by(PostComment.post_id)
    ).all()
    return {pid: count for pid, count in rows}


def _liked_by(db: Session, user: User, post_ids: list[int]) -> set[int]:
    if not post_ids:
        return set()
    rows = db.execute(
        select(PostReaction.post_id).where(
            PostReaction.user_id == user.id, PostReaction.post_id.in_(post_ids)
        )
    ).scalars().all()
    return set(rows)


def _to_card(post: Post, author: User, user: User, likes: int, comments: int, liked: bool) -> PostCard:
    return PostCard(
        id=post.id, post_type=post.post_type, content=post.content,
        image_url=post.image_url, status=post.status, created_at=post.created_at,
        author_id=author.id, author_name=author.display_name,
        author_avatar_url=author.avatar_url,
        like_count=likes, comment_count=comments,
        liked_by_me=liked, is_mine=post.author_id == user.id,
    )


def create_post(db: Session, user: User, data: PostCreate) -> PostCard:
    """UC-49 — đăng bài (E1 nội dung rỗng đã chặn ở schema min_length=1)."""
    if not data.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nội dung bài viết không được để trống"
        )

    post = Post(
        author_id=user.id,
        post_type=data.post_type,
        content=data.content.strip(),
        image_url=data.image_url,
        # Q3: bật kiểm duyệt ở UC-81 thì bài phải chờ Admin duyệt (UC-77)
        status=STATUS_PENDING if config_service.get_bool("require_post_approval") else STATUS_APPROVED,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _to_card(post, user, user, likes=0, comments=0, liked=False)


def list_feed(
    db: Session,
    user: User,
    *,
    post_type: str | None = None,
    author_id: int | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PostListResponse:
    """UC-49 — bảng tin: chỉ bài đã duyệt & chưa xóa, mới nhất trước."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = [Post.deleted_at.is_(None), Post.status == STATUS_APPROVED]
    if post_type:
        filters.append(Post.post_type == post_type)
    if author_id:
        filters.append(Post.author_id == author_id)

    total = db.execute(select(func.count()).select_from(Post).where(*filters)).scalar_one()
    rows = db.execute(
        select(Post, User)
        .join(User, User.id == Post.author_id)
        .where(*filters)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    post_ids = [p.id for p, _ in rows]
    likes = _like_counts(db, post_ids)
    comments = _comment_counts(db, post_ids)
    liked = _liked_by(db, user, post_ids)

    items = [
        _to_card(p, author, user, likes.get(p.id, 0), comments.get(p.id, 0), p.id in liked)
        for p, author in rows
    ]
    return PostListResponse(items=items, total=total, page=page, page_size=page_size)


def delete_post(db: Session, user: User, post_id: int) -> None:
    """UC-52 — gỡ bài của chính mình (E1: không phải tác giả -> 403).
    Xóa mềm bài + ẩn bình luận kèm theo."""
    post = get_visible_post(db, post_id)
    if post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bạn chỉ có thể xóa bài của mình"
        )

    now = datetime.now(timezone.utc)
    post.deleted_at = now
    for comment in db.execute(
        select(PostComment).where(
            PostComment.post_id == post.id, PostComment.deleted_at.is_(None)
        )
    ).scalars():
        comment.deleted_at = now
    db.commit()


def add_comment(db: Session, user: User, post_id: int, data: CommentCreate) -> CommentResponse:
    """UC-50 — bình luận vào bài đã hiển thị công khai."""
    post = get_visible_post(db, post_id)
    if not data.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bình luận không được để trống"
        )

    comment = PostComment(post_id=post.id, author_id=user.id, content=data.content.strip())
    db.add(comment)

    # UC-50 bước 3 / UC-61: báo cho tác giả bài (bỏ qua khi tự bình luận bài mình)
    if post.author_id != user.id:
        notification_service.notify(
            db, post.author_id, type_="community",
            title=f"{user.display_name} đã bình luận bài của bạn",
            body=comment.content[:120], link="/community", commit=False,
        )
    db.commit()
    db.refresh(comment)
    return CommentResponse(
        id=comment.id, post_id=post.id, content=comment.content,
        created_at=comment.created_at, author_id=user.id,
        author_name=user.display_name, is_mine=True,
    )


def list_comments(db: Session, user: User, post_id: int) -> list[CommentResponse]:
    post = get_visible_post(db, post_id)
    rows = db.execute(
        select(PostComment, User)
        .join(User, User.id == PostComment.author_id)
        .where(PostComment.post_id == post.id, PostComment.deleted_at.is_(None))
        .order_by(PostComment.created_at, PostComment.id)
    ).all()
    return [
        CommentResponse(
            id=c.id, post_id=post.id, content=c.content, created_at=c.created_at,
            author_id=author.id, author_name=author.display_name,
            is_mine=c.author_id == user.id,
        )
        for c, author in rows
    ]


def toggle_reaction(db: Session, user: User, post_id: int) -> ReactionResponse:
    """UC-51 — bấm thích/bỏ thích (một react/người/bài)."""
    post = get_visible_post(db, post_id)

    reaction = db.execute(
        select(PostReaction).where(
            PostReaction.post_id == post.id, PostReaction.user_id == user.id
        )
    ).scalar_one_or_none()

    if reaction is None:
        db.add(PostReaction(post_id=post.id, user_id=user.id))
        liked = True
        if post.author_id != user.id:
            notification_service.notify(
                db, post.author_id, type_="community",
                title=f"{user.display_name} đã thích bài của bạn",
                link="/community", commit=False,
            )
    else:
        db.delete(reaction)
        liked = False
    db.commit()

    return ReactionResponse(
        post_id=post.id,
        like_count=_like_counts(db, [post.id]).get(post.id, 0),
        liked_by_me=liked,
    )
