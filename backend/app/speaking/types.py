"""Kiểu dữ liệu dùng chung giữa các tầng của module luyện nói.

Dùng dataclass thuần thay vì Pydantic ở tầng lõi: các tầng này phải test được
mà không cần dựng app, và không phụ thuộc vào tầng API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Word:
    """Một từ trong transcript kèm mốc thời gian và độ tin cậy của ASR."""

    text: str
    start: float           # giây
    end: float
    # 0..1 — Whisper trả avg_logprob/probability; tầng ASR quy về thang này
    confidence: float


@dataclass(frozen=True)
class Transcript:
    text: str
    words: list[Word]
    duration_sec: float
    language: str
    # Whisper trả no_speech_prob theo segment; giữ lại để cảnh báo bản ghi im lặng
    no_speech_prob: float = 0.0

    @property
    def word_count(self) -> int:
        return len(self.words)


@dataclass(frozen=True)
class FluencyFeatures:
    """Đặc trưng C1 — tính hoàn toàn từ mốc thời gian, không cần LLM."""

    duration_sec: float
    speech_sec: float
    words_per_minute: float
    pause_ratio: float          # tổng thời gian lặng / tổng thời lượng
    pause_count: int            # số khoảng lặng vượt ngưỡng
    longest_pause_sec: float
    filler_count: int
    filler_per_100_words: float


@dataclass(frozen=True)
class IntelligibilityFeatures:
    """Đặc trưng C2 — suy ra GIÁN TIẾP từ tín hiệu ASR.

    MVP không chấm âm vị (rubric mục 4 C2, ghi chú kỹ thuật). Các trường ở đây
    là proxy: ASR "nghe không ra" thường trùng với chỗ phát âm khó hiểu.
    """

    avg_confidence: float
    low_confidence_ratio: float     # tỉ lệ từ dưới ngưỡng tin cậy
    low_confidence_words: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PronunciationSignal:
    """Đầu ra chuẩn hóa của MỘT bộ chấm phát âm bất kỳ.

    ĐIỂM CẮM v2: bộ chấm âm vị (GOP / wav2vec2) chỉ cần trả về đúng kiểu này là
    thay thế được bộ chấm dựa trên ASR mà không phải sửa tầng scoring.
    """

    score: float                      # 0..1, càng cao càng dễ hiểu
    evidence: list[str]
    # Nguồn tín hiệu: 'asr_confidence' (MVP) | 'gop' | 'wav2vec2' (v2)
    source: str
    detail: dict = field(default_factory=dict)


class PronunciationScorer(Protocol):
    """Giao diện cho bộ chấm phát âm — xem `types.PronunciationSignal`."""

    source: str

    def score(self, transcript: Transcript, audio_path: str) -> PronunciationSignal:
        ...


@dataclass(frozen=True)
class CriterionScore:
    criterion: str            # fluency | pronunciation | grammar_vocab | coherence_task
    level: int                # 1..4
    label: str               # Emerging | Developing | Proficient | Advanced
    evidence: list[str]
    suggestion: str
    # 'rule' = suy từ đặc trưng đo được · 'llm' = Ollama chấm · 'fallback' = LLM
    # không dùng được nên trả mức thận trọng kèm lý do
    scored_by: str
    reason: str = ""


@dataclass(frozen=True)
class SpeakingAssessment:
    transcript: str
    audio_metrics: dict
    scores: dict[str, CriterionScore]
    overall_level: int
    developmental_feedback: str
    warnings: list[str] = field(default_factory=list)
