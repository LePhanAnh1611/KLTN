from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameScore(Base):
    """UC-94 — kỷ lục của một người ở một trò chơi.

    Chỉ giữ điểm cao nhất: bảng xếp hạng không cần lịch sử từng ván, và lưu mọi
    ván sẽ phình nhanh hơn cả INTERACTION mà không ai đọc lại.
    """

    __tablename__ = "game_scores"
    __table_args__ = (UniqueConstraint("user_id", "game", name="uq_game_score_user_game"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    game: Mapped[str] = mapped_column(String(20), nullable=False)
    best_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    best_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    plays: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
