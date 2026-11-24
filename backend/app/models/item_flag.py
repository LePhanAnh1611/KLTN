from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ItemFlag(Base, TimestampMixin):
    """UC-32 — người học TỰ đánh dấu một từ là khó.

    Khác `weak_items` của UC-40/86: cái kia do DKT suy ra từ mastery, cái này là
    cảm nhận chủ quan của người học. Hai nguồn không thay thế nhau — có từ mastery
    cao nhưng người học vẫn thấy khó nhớ, và ngược lại.
    """

    __tablename__ = "item_flags"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_item_flag_user_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
