from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PronunciationAttempt(Base, TimestampMixin):
    """Một lần luyện phát âm được chấm — GỘP cả luyện từ lẫn đọc câu mẫu.

    Một bảng cho hai chế độ (`kind`) thay vì tách đôi: với người học đó là cùng
    một việc "luyện nói từ này", nên lịch sử phải nằm chung một chỗ.

    CỐ Ý KHÔNG nối vào INTERACTION/KNOWLEDGE_STATE: điểm phát âm không đủ tin
    cậy để làm đầu vào cho DKT. Đây là nhật ký tự đánh giá, không phải bằng
    chứng học tập.
    """

    __tablename__ = "pronunciation_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )
    # 'word'     = đọc riêng từ, trình duyệt chấm (Web Speech API)
    # 'sentence' = đọc câu mẫu, máy chủ chấm (Whisper + đối chiếu câu)
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="word", server_default="word", index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)      # 0..100
    transcript: Mapped[str | None] = mapped_column(String(300))      # nghe ra gì
    # Câu mẫu cần đọc — chốt lại tại thời điểm luyện, vì người dùng sửa được
    # `item.example` sau đó và khi ấy kết quả cũ sẽ không còn giải thích được.
    target_text: Mapped[str | None] = mapped_column(Text)
    # Chi tiết chấm của chế độ 'sentence': từng từ, các khía cạnh, số đo âm thanh
    detail: Mapped[dict | None] = mapped_column(JSON)
