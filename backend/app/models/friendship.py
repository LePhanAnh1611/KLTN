from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# pending: đã gửi, chờ trả lời · accepted: đã là bạn · declined: bị từ chối
FRIEND_STATUSES = ("pending", "accepted", "declined")


class Friendship(Base, TimestampMixin):
    """UC-56 — quan hệ bạn bè giữa hai người học.

    Lưu MỘT hàng cho mỗi cặp (người gửi, người nhận) thay vì hai hàng đối xứng:
    hai hàng thì mỗi thao tác phải sửa cả hai và sẽ có lúc lệch. Đổi lại, mọi
    truy vấn "bạn của tôi" phải nhìn cả hai cột — xem `friendship_service`.
    """

    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    requester_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    addressee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", index=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
