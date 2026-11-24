from __future__ import annotations

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemConfig(Base, TimestampMixin):
    """UC-81 — tham số vận hành chỉnh được lúc chạy (θ_review, vùng vừa sức,
    quy đổi XP...). Giá trị lưu dạng chuỗi; kiểu & khoảng an toàn khai báo trong
    `config_service.CONFIG_DEFS`. Key nào chưa có bản ghi thì dùng mặc định."""

    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
