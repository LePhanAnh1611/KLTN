from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WordSetTag(Base):
    """UC-96 — nhãn lọc chéo của bộ từ vựng.

    Khác `WordSet.category` (UC-76): danh mục do Admin quản lý và mỗi bộ chỉ có
    một; nhãn do người tạo bộ tự đặt và một bộ có nhiều nhãn.
    """

    __tablename__ = "word_set_tags"
    __table_args__ = (UniqueConstraint("word_set_id", "tag", name="uq_word_set_tag"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    word_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("word_sets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tag: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
