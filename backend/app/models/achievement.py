from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Achievement(TimestampMixin, Base):
    """UC-79 — định nghĩa huy hiệu cho UC-48.

    Điều kiện đạt mô tả bằng dữ liệu (`condition_key` >= `threshold`) thay vì
    code, để Admin thêm/sửa được mà không phải deploy lại. `code` là khóa nghiệp
    vụ, USER_ACHIEVEMENTS tham chiếu tới nó."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_key: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
