"""Điều phối toàn bộ: audio → transcript → đặc trưng → chấm → nhận xét.

Pipeline theo đúng rubric mục 5:
    audio → Whisper (transcript + timing + confidence)
          → [đặc trưng fluency/intelligibility]  +  [Ollama chấm C3, C4]
          → tổng hợp mức từng tiêu chí
          → Ollama sinh nhận xét phát triển

Mọi phụ thuộc nặng (ASR engine, bộ chấm phát âm) đều tiêm từ ngoài vào để test
chạy được mà không cần model — và để v2 cắm bộ chấm âm vị mà không sửa file này.
"""
from __future__ import annotations

import logging

from app.speaking.asr.base import AsrEngine
from app.speaking.features import fluency as fluency_features
from app.speaking.features.intelligibility import AsrConfidenceScorer
from app.speaking.feedback.composer import compose
from app.speaking.rubric import Rubric, load_rubric
from app.speaking.rubric.thresholds import is_calibrated, load_thresholds
from app.speaking.scoring import llm_scorer, rule_scorer
from app.speaking.scoring.aggregate import overall_level
from app.speaking.types import (
    PronunciationScorer,
    SpeakingAssessment,
    Transcript,
)

logger = logging.getLogger(__name__)


def _default_asr() -> AsrEngine:
    """Import muộn: `whisper_engine` kéo theo faster-whisper khi thực sự dùng."""
    from app.speaking.asr.whisper_engine import WhisperEngine

    return WhisperEngine()


def _quality_warnings(transcript: Transcript) -> list[str]:
    """Cảnh báo khi bản ghi không đủ để chấm tin cậy (rubric mục 9).

    Vẫn trả kết quả — nhưng nói thẳng là kém tin cậy, thay vì im lặng đưa ra một
    con số mà người học sẽ tin.
    """
    gates = load_thresholds()["quality_gates"]
    warnings: list[str] = []

    if transcript.duration_sec < float(gates["min_duration_sec"]):
        warnings.append(
            f"Bản ghi chỉ dài {transcript.duration_sec:.1f}s - quá ngắn để đánh giá "
            "đáng tin. Hãy nói ít nhất "
            f"{gates['min_duration_sec']:.0f}s."
        )
    if transcript.word_count < int(gates["min_words"]):
        warnings.append(
            f"Chỉ nhận dạng được {transcript.word_count} từ - kết quả chấm gần như "
            "không có ý nghĩa."
        )
    if transcript.no_speech_prob > float(gates["max_no_speech_prob"]):
        warnings.append(
            "Phần lớn bản ghi có vẻ không phải giọng nói (im lặng hoặc tiếng ồn). "
            "Kiểm tra lại micro."
        )
    if transcript.words:
        average = sum(w.confidence for w in transcript.words) / len(transcript.words)
        if average < float(gates["unreliable_avg_confidence"]):
            warnings.append(
                f"Độ tin cậy nhận dạng rất thấp ({average:.0%}). Có thể do ồn nền hoặc "
                "micro kém - điểm Độ dễ hiểu lúc này chưa phản ánh đúng phát âm."
            )

    if not is_calibrated():
        warnings.append(
            "Rubric chưa được calibrate với người chấm thật (mục 8 của rubric). "
            "Hãy đọc kết quả như một tham chiếu định hướng, không phải điểm chuẩn."
        )
    return warnings


def assess(
    audio_path: str,
    task_prompt: str,
    *,
    language: str | None = None,
    weights: dict[str, float] | None = None,
    asr: AsrEngine | None = None,
    pronunciation_scorer: PronunciationScorer | None = None,
    rubric: Rubric | None = None,
    use_llm: bool = True,
) -> SpeakingAssessment:
    """Chấm một bài nói.

    `pronunciation_scorer` để mặc định là bộ dựa trên confidence của ASR (MVP).
    v2 truyền vào bộ chấm âm vị (GOP/wav2vec2) — chỉ cần cài `PronunciationScorer`.
    """
    rubric = rubric or load_rubric()
    engine = asr or _default_asr()
    pron_scorer = pronunciation_scorer or AsrConfidenceScorer()

    transcript = engine.transcribe(audio_path, language=language)
    warnings = _quality_warnings(transcript)

    # --- C1, C2: từ số đo, tất định ---
    fluency = fluency_features.extract(transcript)
    pron_signal = pron_scorer.score(transcript, audio_path)

    scores = {
        "fluency": rule_scorer.score_fluency(fluency, rubric),
        "pronunciation": rule_scorer.score_pronunciation(pron_signal, rubric, transcript),
    }

    # --- C3, C4: LLM, mỗi tiêu chí một lần gọi riêng (rubric mục 7.1) ---
    if use_llm:
        scores["grammar_vocab"] = llm_scorer.score_criterion(
            rubric, "grammar_vocab", transcript.text,
        )
        scores["coherence_task"] = llm_scorer.score_criterion(
            rubric, "coherence_task", transcript.text, task_prompt,
        )
    else:
        for key in ("grammar_vocab", "coherence_task"):
            scores[key] = llm_scorer._fallback(rubric, key, "đã tắt LLM (use_llm=False)")

    if any(s.scored_by == "fallback" for s in scores.values()):
        warnings.append(
            "Một số tiêu chí chưa chấm được vì mô hình ngôn ngữ cục bộ không sẵn sàng. "
            "Kiểm tra Ollama đang chạy và model đã được tải."
        )

    overall = overall_level(scores, weights)

    return SpeakingAssessment(
        transcript=transcript.text,
        audio_metrics={
            "duration_sec": fluency.duration_sec,
            "speech_sec": fluency.speech_sec,
            "words_per_minute": fluency.words_per_minute,
            "pause_ratio": fluency.pause_ratio,
            "pause_count": fluency.pause_count,
            "longest_pause_sec": fluency.longest_pause_sec,
            "filler_count": fluency.filler_count,
            "filler_per_100_words": fluency.filler_per_100_words,
            "asr_avg_confidence": round(pron_signal.score, 4),
            "word_count": transcript.word_count,
            "language": transcript.language,
            "pronunciation_source": pron_signal.source,
        },
        scores=scores,
        overall_level=overall,
        developmental_feedback=compose(scores, rubric, overall, use_llm=use_llm),
        warnings=warnings,
    )
