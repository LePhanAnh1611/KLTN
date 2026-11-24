from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Item(TimestampMixin, Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    word_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("word_sets.id"), nullable=False, index=True
    )
    word: Mapped[str] = mapped_column(String(200), nullable=False)
    phonetic: Mapped[str | None] = mapped_column(String(200))
    part_of_speech: Mapped[str | None] = mapped_column(String(50))
    meaning: Mapped[str] = mapped_column(Text, nullable=False)
    example: Mapped[str | None] = mapped_column(Text)
    #: Bản dịch tiếng Việt của `example`; chỉ có với item seed từ bộ nền.
    example_vi: Mapped[str | None] = mapped_column(Text)

    # Nguồn gốc nội dung — chỉ có với item do hệ thống seed từ bộ từ nền.
    # NULL = người học tự nhập (UC-14/15/87): họ tự viết thì không cần hệ thống
    # chứng nhận, và gắn cờ lên chữ của chính họ là xúc phạm.
    #: 'confirmed' | 'single-source' | 'needs-review' | 'llm'
    meaning_confidence: Mapped[str | None] = mapped_column(String(20))
    #: 'fvdp' | 'llm' | 'manual' | 'user'
    meaning_source: Mapped[str | None] = mapped_column(String(20))
    #: 'fvdp' | 'llm' | 'manual'
    example_source: Mapped[str | None] = mapped_column(String(20))

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
