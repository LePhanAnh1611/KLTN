from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WordSet(TimestampMixin, Base):
    __tablename__ = "word_sets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[str | None] = mapped_column(String(20))
    #: Mức CEFR của cả bộ (A1…C2). NULL = bộ người học tự tạo, không khai mức.
    #: Khác `difficulty`: difficulty chỉ có 3 nhóm nên A1 và A2 gộp làm một.
    cefr_level: Mapped[str | None] = mapped_column(String(10))
    is_public: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_featured: Mapped[bool] = mapped_column(default=False, server_default="false")
    origin_set_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("word_sets.id", ondelete="SET NULL")
    )
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # UC-87 — truy nguyên bộ từ đến từ đâu: 'manual' | 'pdf' | 'csv' | 'download'
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    source_filename: Mapped[str | None] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
