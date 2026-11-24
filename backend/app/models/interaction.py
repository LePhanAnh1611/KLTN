from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (UniqueConstraint("session_id", "client_answer_id", name="uq_interaction_client_answer"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sessions.id"))
    is_correct: Mapped[bool] = mapped_column(nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    exercise_format: Mapped[str | None] = mapped_column(String(30))
    client_answer_id: Mapped[str | None] = mapped_column(String(36))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    # UC-70 — P(đúng) hệ thống nắm giữ NGAY TRƯỚC khi thấy kết quả lượt này.
    # NULL = chưa có dự đoán nào (lần đầu gặp từ, hoặc mô hình không biết từ đó);
    # phải phân biệt được với một dự đoán thật sự bằng 0.5.
    predicted_mastery: Mapped[float | None] = mapped_column(Float)
    #: 'model' = DKT chấm · 'prior' = giá trị cold-start · None = chưa có gì
    prediction_source: Mapped[str | None] = mapped_column(String(10))
    #: Pilot — vì sao từ này được đưa ra: 'band' (vừa sức, BR-03) · 'explore'
    #: (ngẫu nhiên, để đo không thiên lệch) · 'review' · 'validation' · None (khác)
    selection_reason: Mapped[str | None] = mapped_column(String(12))
    #: Lượt bị loại khỏi DKT và mọi phân tích vì dữ liệu ghi sai (không phải lỗi
    #: của người học). Bản ghi vẫn giữ (BR-05) để truy vết; NULL = lượt hợp lệ.
    #: Ví dụ 'grading_bug_2026-10-26' — xem app/scripts/fix_grading_bug_20261026.py.
    excluded_reason: Mapped[str | None] = mapped_column(String(40))
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def counted_interaction():
    """Điều kiện "lượt được tính": dùng cho đầu vào DKT, mastery, lịch ôn và mọi
    số đo thực nghiệm. Lượt có `excluded_reason` coi như chưa từng xảy ra."""
    return Interaction.excluded_reason.is_(None)
