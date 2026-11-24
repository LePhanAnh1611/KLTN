from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ShadowingVideo(Base, TimestampMixin):
    """Một video YouTube dùng để luyện shadowing (UC-97).

    Hai nguồn trong CÙNG một bảng (`source`):
      - 'catalog': kho có sẵn do admin thêm, duyệt rồi xuất bản cho mọi người.
      - 'user'   : người học tự dán link, chỉ chính người đó thấy (`owner_id`).

    KHÔNG lưu audio/video — chỉ nhúng trình phát chính thức của YouTube. Phụ đề
    đã cắt câu nằm ở `segments` (cache để học), không đưa vào repo.
    """

    __tablename__ = "shadowing_videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Không unique: cùng một video có thể vừa nằm trong kho vừa là video riêng
    # của người học thêm trước khi admin đưa vào kho.
    youtube_id: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(200))

    topic: Mapped[str | None] = mapped_column(String(100), index=True)
    cefr_level: Mapped[str | None] = mapped_column(String(2), index=True)
    words_per_minute: Mapped[float | None] = mapped_column(Float)
    duration_sec: Mapped[float | None] = mapped_column(Float)

    # 'manual' (người đăng tạo) | 'generated' (tự động) | 'upload' (file .srt/.vtt)
    caption_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    # [{"index", "start", "end", "text"}] — mốc thời gian tính bằng giây
    segments: Mapped[list] = mapped_column(JSON, nullable=False)
    # Hồ sơ từ vựng: số từ theo từng mức CEFR, tỉ lệ tra được...
    vocab_profile: Mapped[dict | None] = mapped_column(JSON)

    # 'public-domain' | 'cc-by' | 'cc-by-sa' | 'youtube-standard'
    license: Mapped[str | None] = mapped_column(String(30))
    attribution: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    # 'draft' | 'published' — video của người học luôn 'published'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft", index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Xóa mềm: giữ lịch sử luyện (shadowing_attempts) còn giải thích được
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShadowingAttempt(Base, TimestampMixin):
    """Một lần nhại lại MỘT câu của video, đã chấm.

    CỐ Ý KHÔNG nối vào INTERACTION/KNOWLEDGE_STATE: một câu nhại lại không phải
    lượt trả lời về một từ cụ thể, đưa vào DKT là làm bẩn dữ liệu mô hình.
    """

    __tablename__ = "shadowing_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shadowing_videos.id"), nullable=False, index=True
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Câu gốc chốt tại thời điểm luyện — admin sửa câu sau đó thì kết quả cũ
    # vẫn giải thích được.
    target_text: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text)

    accuracy: Mapped[float] = mapped_column(Float, nullable=False)       # 0..1
    clarity: Mapped[float] = mapped_column(Float, nullable=False)        # 0..1
    # Tốc độ người học ÷ tốc độ câu gốc; None khi không đo được
    speed_ratio: Mapped[float | None] = mapped_column(Float)
    overall_level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..4
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Từng từ, các khía cạnh, số đo âm thanh — như PronunciationAttempt.detail
    detail: Mapped[dict | None] = mapped_column(JSON)
