from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WordSetRating(TimestampMixin, Base):
    """UC-23 đánh giá bộ từ — một đánh giá/người/bộ (sửa = ghi đè)."""

    __tablename__ = "word_set_ratings"
    __table_args__ = (
        UniqueConstraint("word_set_id", "user_id", name="uq_word_set_rating"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    word_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("word_sets.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..5
    comment: Mapped[str | None] = mapped_column(Text)
