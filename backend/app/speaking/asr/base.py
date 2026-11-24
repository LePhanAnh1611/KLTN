"""Giao diện ASR — tách khỏi faster-whisper để test được mà không cần model.

Mọi tầng phía sau chỉ biết `Transcript`, không biết engine nào tạo ra nó. Đổi
sang engine khác (whisper.cpp, wav2vec2...) chỉ là viết một lớp mới ở đây.
"""
from __future__ import annotations

from typing import Protocol

from app.speaking.types import Transcript


class AsrEngine(Protocol):
    name: str

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        ...


class AsrUnavailable(RuntimeError):
    """ASR không chạy được (thiếu thư viện, thiếu model, file hỏng).

    Ném lỗi thay vì degrade mềm như DKT: không có transcript thì KHÔNG có gì để
    chấm cả. Trả về một kết quả rỗng sẽ là bịa điểm cho người học.
    """
