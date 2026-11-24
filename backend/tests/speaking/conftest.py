"""Đồ giả cho module luyện nói.

Toàn bộ test chạy KHÔNG cần faster-whisper và KHÔNG cần Ollama: tầng lõi chỉ
phụ thuộc vào hai giao diện (`AsrEngine`, `PronunciationScorer`) nên thay bằng
đồ giả là đủ. Nhờ vậy CI không phải tải model hàng trăm MB.
"""
from __future__ import annotations

import pytest

from app.speaking.types import Transcript, Word


def make_transcript(
    spec: list[tuple[str, float, float, float]],
    *,
    duration: float | None = None,
    language: str = "en",
    no_speech_prob: float = 0.0,
) -> Transcript:
    """Dựng Transcript từ [(text, start, end, confidence)]."""
    words = [Word(text=t, start=s, end=e, confidence=c) for t, s, e, c in spec]
    total = duration if duration is not None else (words[-1].end if words else 0.0)
    return Transcript(
        text=" ".join(w.text for w in words),
        words=words,
        duration_sec=total,
        language=language,
        no_speech_prob=no_speech_prob,
    )


def evenly_spaced(
    text: str, *, wpm: float, confidence: float = 0.95, gap: float = 0.0,
) -> Transcript:
    """Bài nói đều nhịp ở tốc độ cho trước — dùng để kiểm ngưỡng fluency."""
    words = text.split()
    seconds_per_word = 60.0 / wpm
    spec: list[tuple[str, float, float, float]] = []
    cursor = 0.0
    for word in words:
        spec.append((word, cursor, cursor + seconds_per_word, confidence))
        cursor += seconds_per_word + gap
    return make_transcript(spec, duration=cursor)


class FakeAsr:
    """ASR giả: trả về đúng transcript đã dựng sẵn."""

    name = "fake"

    def __init__(self, transcript: Transcript):
        self._transcript = transcript
        self.calls: list[tuple[str, str | None]] = []

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        self.calls.append((audio_path, language))
        return self._transcript


class FakeGopScorer:
    """Bộ chấm phát âm giả cho v2 — chứng minh điểm cắm hoạt động."""

    source = "gop"

    def __init__(self, score: float = 0.8):
        self._score = score

    def score(self, transcript, audio_path):
        from app.speaking.types import PronunciationSignal

        return PronunciationSignal(
            score=self._score,
            evidence=[f"GOP trung bình {self._score:.2f}"],
            source=self.source,
            detail={"low_confidence_ratio": 0.0},
        )


@pytest.fixture
def fluent_transcript() -> Transcript:
    """Bài nói trôi chảy: nhanh vừa, ít nghỉ, không từ đệm, ASR nghe rõ."""
    return evenly_spaced(
        "The place I enjoy most is a small bookshop near my university because "
        "it is quiet and the owner always recommends something unexpected",
        wpm=130, confidence=0.95,
    )


@pytest.fixture
def halting_transcript() -> Transcript:
    """Bài nói ngập ngừng: chậm, nghỉ dài, nhiều từ đệm, ASR nghe không chắc."""
    return make_transcript([
        ("I", 0.0, 0.4, 0.9),
        ("uh", 0.4, 0.9, 0.8),
        ("like", 2.6, 3.1, 0.45),      # nghỉ 1.7s
        ("um", 3.1, 3.7, 0.8),
        ("the", 6.0, 6.3, 0.4),        # nghỉ 2.3s
        ("beach", 6.3, 7.0, 0.35),
    ], duration=8.0)
