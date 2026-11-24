"""UC-97 — Shadowing theo phụ đề video YouTube.

Các mảnh thuần (không đụng DB, test được độc lập):
  - youtube.py   : nhận dạng link, lấy phụ đề + tiêu đề từ YouTube
  - subtitles.py : đọc file .srt / .vtt (phương án dự phòng)
  - segmenter.py : gộp mảnh phụ đề thành câu luyện
  - profile.py   : hồ sơ từ vựng CEFR + tốc độ nói
Nghiệp vụ có DB nằm ở `app/services/shadowing_service.py`.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Snippet:
    """Một mảnh phụ đề thô: chữ + mốc bắt đầu + độ dài (giây)."""

    text: str
    start: float
    duration: float


class CaptionError(Exception):
    """Không lấy được phụ đề. `blocked=True` = lỗi phía YouTube chặn (503),
    ngược lại là lỗi của chính video/link (422)."""

    def __init__(self, message: str, *, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked
