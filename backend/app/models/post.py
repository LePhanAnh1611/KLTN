from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Post(TimestampMixin, Base):
    """UC-49 bài viết cộng đồng. `status` phục vụ Q3 (duyệt trước hiển thị):
    hiện `settings.require_post_approval=False` nên bài vào thẳng 'approved';
    khi làm UC-77 (Admin kiểm duyệt) chỉ cần bật cờ. Xóa mềm (Q6) qua deleted_at."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    post_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="approved", server_default="approved"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
