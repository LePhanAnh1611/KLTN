"""C2 Intelligibility — proxy độ dễ hiểu từ confidence của ASR (rubric mục 5).

Giả định nền: chỗ nào Whisper "nghe không ra" thì người nghe thật cũng vất vả.
Đây là XẤP XỈ, không phải đo phát âm — rubric mục 4/C2 và mục 9 đã nói rõ giới
hạn này và đầu ra của module cũng phải nhắc lại.

`AsrConfidenceScorer` cài `types.PronunciationScorer`, nên bộ chấm âm vị ở v2
chỉ cần cài cùng giao diện là thay thế được (xem `pipeline.assess`).
"""
from __future__ import annotations

from app.speaking.rubric.thresholds import load_thresholds
from app.speaking.types import (
    IntelligibilityFeatures,
    PronunciationSignal,
    Transcript,
)


def extract(transcript: Transcript) -> IntelligibilityFeatures:
    config = load_thresholds()["intelligibility"]
    low_threshold = float(config["low_confidence_word_threshold"])
    max_examples = int(config["max_low_confidence_examples"])

    words = transcript.words
    if not words:
        return IntelligibilityFeatures(
            avg_confidence=0.0, low_confidence_ratio=0.0, low_confidence_words=[],
        )

    confidences = [w.confidence for w in words]
    low = [w for w in words if w.confidence < low_threshold]
    # Sắp theo confidence tăng dần: từ khó hiểu NHẤT lên đầu, vì đó là chỗ người
    # học nên sửa trước.
    low.sort(key=lambda w: w.confidence)

    return IntelligibilityFeatures(
        avg_confidence=round(sum(confidences) / len(confidences), 4),
        low_confidence_ratio=round(len(low) / len(words), 4),
        low_confidence_words=[w.text for w in low[:max_examples]],
    )


class AsrConfidenceScorer:
    """Bộ chấm phát âm mặc định của MVP — chỉ dùng tín hiệu ASR.

    ĐIỂM CẮM v2: viết một lớp khác có cùng `source` + `score()` (GOP hoặc
    wav2vec2), truyền vào `pipeline.assess(pronunciation_scorer=...)`. Không cần
    sửa scoring/aggregate/feedback.
    """

    source = "asr_confidence"

    def score(self, transcript: Transcript, audio_path: str) -> PronunciationSignal:
        features = extract(transcript)

        evidence: list[str] = [
            f"Độ tin cậy nhận dạng trung bình {features.avg_confidence:.0%}.",
        ]
        if features.low_confidence_words:
            listed = ", ".join(f"“{w}”" for w in features.low_confidence_words)
            evidence.append(
                f"{features.low_confidence_ratio:.0%} số từ máy nghe không chắc, "
                f"ví dụ: {listed}."
            )
        else:
            evidence.append("Không có từ nào máy nghe không chắc.")

        return PronunciationSignal(
            score=features.avg_confidence,
            evidence=evidence,
            source=self.source,
            detail={
                "avg_confidence": features.avg_confidence,
                "low_confidence_ratio": features.low_confidence_ratio,
                "low_confidence_words": features.low_confidence_words,
            },
        )
