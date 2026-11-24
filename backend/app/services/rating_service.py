"""UC-23 — đánh giá / xếp hạng bộ từ công khai.

Một đánh giá/người/bộ (gửi lại = sửa, luồng 1a). E1: chưa tải bộ từ thì không
được đánh giá (chống spam). Điểm trung bình nuôi chỉ số "phổ biến" của UC-19.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.word_set import WordSet
from app.models.word_set_rating import WordSetRating
from app.schemas.rating import RatingItem, RatingRequest, RatingSummary
from app.services.word_set_service import get_public_word_set

RATING_LIST_LIMIT = 20


def has_downloaded(db: Session, user: User, word_set_id: int) -> bool:
    """Đã có bản sao (snapshot Q1) của bộ này trong thư viện chưa."""
    return db.execute(
        select(WordSet.id).where(
            WordSet.owner_id == user.id,
            WordSet.origin_set_id == word_set_id,
            WordSet.deleted_at.is_(None),
        )
    ).first() is not None


def rating_map(db: Session, word_set_ids: list[int]) -> dict[int, tuple[float, int]]:
    """{word_set_id: (điểm trung bình, số lượt)} — gộp 1 truy vấn, tránh N+1."""
    if not word_set_ids:
        return {}
    rows = db.execute(
        select(
            WordSetRating.word_set_id,
            func.avg(WordSetRating.stars),
            func.count(WordSetRating.id),
        )
        .where(WordSetRating.word_set_id.in_(word_set_ids))
        .group_by(WordSetRating.word_set_id)
    ).all()
    return {ws_id: (round(float(avg), 2), count) for ws_id, avg, count in rows}


def upsert_rating(
    db: Session, user: User, word_set_id: int, data: RatingRequest
) -> RatingSummary:
    """Chấm sao lần đầu hoặc sửa đánh giá đã gửi (luồng 1a)."""
    get_public_word_set(db, word_set_id)
    if not has_downloaded(db, user, word_set_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn cần tải bộ từ vựng về trước khi đánh giá",
        )

    rating = db.execute(
        select(WordSetRating).where(
            WordSetRating.word_set_id == word_set_id,
            WordSetRating.user_id == user.id,
        )
    ).scalar_one_or_none()

    if rating is None:
        rating = WordSetRating(
            word_set_id=word_set_id, user_id=user.id,
            stars=data.stars, comment=data.comment,
        )
        db.add(rating)
    else:
        rating.stars = data.stars
        rating.comment = data.comment

    db.commit()
    return get_summary(db, user, word_set_id)


def get_summary(db: Session, user: User, word_set_id: int) -> RatingSummary:
    """Điểm trung bình + đánh giá của chính mình + vài nhận xét gần đây."""
    get_public_word_set(db, word_set_id)

    avg, count = rating_map(db, [word_set_id]).get(word_set_id, (None, 0))

    mine = db.execute(
        select(WordSetRating).where(
            WordSetRating.word_set_id == word_set_id,
            WordSetRating.user_id == user.id,
        )
    ).scalar_one_or_none()

    rows = db.execute(
        select(WordSetRating, User.display_name)
        .join(User, User.id == WordSetRating.user_id)
        .where(WordSetRating.word_set_id == word_set_id)
        .order_by(WordSetRating.updated_at.desc())
        .limit(RATING_LIST_LIMIT)
    ).all()

    return RatingSummary(
        average=avg,
        count=count,
        my_stars=mine.stars if mine else None,
        my_comment=mine.comment if mine else None,
        can_rate=has_downloaded(db, user, word_set_id),
        items=[
            RatingItem(
                user_name=name, stars=r.stars, comment=r.comment, created_at=r.created_at
            )
            for r, name in rows
        ],
    )
