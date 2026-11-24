from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LearningStage(Base, TimestampMixin):
    """UC-84 — một chặng trên bản đồ lộ trình, gắn với đúng một bộ từ.

    Chỉ thêm bảng này; KHÔNG đụng schema học tập hiện có — trạng thái chặng suy ra
    lúc chạy từ KNOWLEDGE_STATE (UC-64) + gợi ý vừa sức (UC-65) + trình độ đầu
    vào (UC-11)."""

    __tablename__ = "learning_stages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("word_sets.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    #: Phiên bản lộ trình. 1 = bản đồ gốc (cắt theo tần suất, đang dùng cho
    #: pilot); 2 = hai track chủ đề + cốt lõi. Người học chỉ thấy chặng cùng
    #: phiên bản với `users.roadmap_version` — đổi lộ trình KHÔNG đụng tiến độ
    #: (bản sao, Interaction, KNOWLEDGE_STATE) của người đang học bản cũ.
    roadmap_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1", index=True
    )
    #: Chỉ v2: 'topic' | 'core'. NULL ở v1.
    track: Mapped[str | None] = mapped_column(String(20))
    #: Chỉ track 'topic': tên chủ đề (Threshold / Core Inventory, CEFR-J).
    topic: Mapped[str | None] = mapped_column(String(100))
