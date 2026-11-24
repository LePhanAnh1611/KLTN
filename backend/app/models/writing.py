from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WritingSubmission(Base, TimestampMixin):
    """UC-37 — một bài dịch Việt→Anh đã nộp và được chấm."""

    __tablename__ = "writing_submissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    prompt_vi: Mapped[str] = mapped_column(Text, nullable=False)
    answer_en: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)          # 0..100, None = chưa chấm được
    feedback: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)        # bản gợi ý viết lại
    # Ai chấm: 'llm' hoặc 'heuristic' (khi không có LLM) — người học phải biết
    # nhận xét mình đang đọc đến từ đâu.
    grader: Mapped[str] = mapped_column(String(20), nullable=False, default="heuristic")


class SentenceNote(Base, TimestampMixin):
    """UC-38 — sổ tay câu: câu hay/khó người học tự lưu lại."""

    __tablename__ = "sentence_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    text_vi: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    # Lưu từ bài luyện viết nào (nếu có) — để mở lại xem nhận xét gốc
    submission_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("writing_submissions.id")
    )
