from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RolePermission(TimestampMixin, Base):
    """UC-74 — quyền được gán cho từng vai trò.

    Danh mục quyền khai báo trong `permission_service.PERMISSIONS` (gắn với
    endpoint nên phải khớp code); bảng này chỉ lưu vai trò nào có quyền nào."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "permission", name="uq_role_permission"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(50), nullable=False)
