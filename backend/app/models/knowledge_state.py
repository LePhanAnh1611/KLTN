from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeState(Base):
    __tablename__ = "knowledge_states"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_knowledge_state_user_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=False, index=True)
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
