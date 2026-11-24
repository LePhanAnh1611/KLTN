from __future__ import annotations

from datetime import date as date_

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ChallengeClaim(Base, TimestampMixin):
    """UC-44 — một lần người học NHẬN thưởng của thử thách ngày.

    Chỉ lưu việc đã nhận thưởng, KHÔNG lưu định nghĩa thử thách: đề bài sinh lại
    được từ ngày + cấu hình, còn tiến độ đọc thẳng từ INTERACTION/SESSION đã có.
    Lưu thêm bảng định nghĩa chỉ tạo ra hai nguồn sự thật phải đồng bộ với nhau.
    """

    __tablename__ = "challenge_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_date", "code", name="uq_claim_user_date_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    challenge_date: Mapped[date_] = mapped_column(Date, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
