from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


class PlacementQuestion(Base, TimestampMixin):
    """UC-11 — ngân hàng câu hỏi kiểm tra trình độ đầu vào.

    Tách khỏi ITEM (nội dung học của người dùng) vì câu hỏi placement là dữ liệu
    hệ thống, gắn nhãn CEFR để chọn "tập item trải đều các mức" (bước 1 UC-11)."""

    __tablename__ = "placement_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cefr_level: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    word: Mapped[str] = mapped_column(String(200), nullable=False)
    correct_meaning: Mapped[str] = mapped_column(String(300), nullable=False)
    distractors: Mapped[list] = mapped_column(JSON, nullable=False)  # 3 nghĩa nhiễu
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class PlacementAttempt(Base, TimestampMixin):
    """UC-11 — một lần làm bài kiểm tra đầu vào.

    Giữ lại số câu đúng theo từng mức để giải thích được kết quả ước lượng
    (và để E1: thoát giữa chừng vẫn còn phần đã làm)."""

    __tablename__ = "placement_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", server_default="completed"
    )  # completed | skipped (luồng thay thế 1a "Tôi mới bắt đầu")
    answered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_level: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    estimated_level: Mapped[str] = mapped_column(String(5), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
