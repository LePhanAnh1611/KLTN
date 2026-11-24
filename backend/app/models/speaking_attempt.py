from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SpeakingAttempt(Base, TimestampMixin):
    """Một lần luyện nói đã được chấm.

    CỐ Ý KHÔNG lưu file audio: cam kết privacy của module là giọng người học
    không nằm lại trên máy chủ (xem `docs/speaking-module.md`). Chỉ giữ transcript
    và kết quả chấm.

    Vẫn KHÔNG nối vào DKT: bảng này không tham chiếu ITEM/KNOWLEDGE_STATE, nên
    điểm nói không lọt vào lộ trình học. Muốn nối ở giai đoạn sau thì thêm bảng
    ánh xạ riêng, không sửa bảng này.

    `scores` lưu nguyên khối JSON thay vì tách 4 cột × 4 trường: rubric còn đang
    ở version 0.1 và mục 8 nói rõ sẽ đổi sau khi calibrate. Tách cột bây giờ là
    tự trói mình vào một phiên bản rubric chưa ổn định.
    """

    __tablename__ = "speaking_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )

    task_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    overall_level: Mapped[int] = mapped_column(Integer, nullable=False)
    # Bốn tiêu chí, mỗi tiêu chí {level,label,evidence,suggestion,scored_by,reason}
    scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    audio_metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    developmental_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Phiên bản rubric lúc chấm — sau khi calibrate lại, số cũ và mới KHÔNG so
    # sánh trực tiếp được với nhau (rubric mục 8).
    rubric_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Vài chỉ số rút ra cột riêng để vẽ biểu đồ tiến bộ mà không phải mở JSON
    words_per_minute: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    asr_avg_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class SpeakingAppeal(Base, TimestampMixin):
    """Người học phản hồi/khiếu nại một kết quả chấm — rubric mục 9.

    Đây là vòng phản hồi để calibrate rubric: chỗ người học thấy chấm sai chính
    là chỗ descriptor còn mơ hồ. Không tự động sửa điểm — chỉ ghi nhận để người
    làm rubric xem lại.
    """

    __tablename__ = "speaking_appeals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("speaking_attempts.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    # Tiêu chí bị khiếu nại, hoặc 'overall' nếu là kết quả chung
    criterion: Mapped[str] = mapped_column(String(30), nullable=False)
    # Mức người học tự cho là đúng — so với mức hệ thống chấm để đo độ lệch
    expected_level: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    # open -> reviewed: người quản trị rubric đã xem
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open", index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
