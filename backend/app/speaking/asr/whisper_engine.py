"""Wrapper faster-whisper: audio → transcript + mốc thời gian từng từ + confidence.

Chạy LOCAL, không gọi API ngoài. Model nạp một lần rồi giữ trong tiến trình:
nạp model là phần tốn nhất (vài giây tới vài chục giây), không thể trả giá đó
cho từng request.

`faster_whisper` được import BÊN TRONG hàm, có chủ đích: thư viện này kéo theo
ctranslate2 và trọng số hàng trăm MB. Import ở đầu file sẽ làm cả backend không
khởi động được trên máy chưa cài — trong khi phần còn lại của app không cần nó.
"""
from __future__ import annotations

import logging
import math
import threading

from app.speaking.asr.base import AsrUnavailable
from app.speaking.config import speaking_settings
from app.speaking.types import Transcript, Word

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _load_model():
    """Nạp (hoặc lấy lại) model. Có khóa vì uvicorn chạy nhiều luồng."""
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AsrUnavailable(
                "Chưa cài faster-whisper. Chạy: pip install -r requirements-speaking.txt"
            ) from exc

        settings = speaking_settings()
        logger.info(
            "Nạp Whisper model=%s device=%s compute_type=%s",
            settings.whisper_model, settings.whisper_device, settings.whisper_compute_type,
        )
        try:
            _model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
                download_root=settings.whisper_download_root or None,
            )
        except Exception as exc:                       # noqa: BLE001
            raise AsrUnavailable(f"Không nạp được Whisper model: {exc}") from exc

    return _model


def reset_model() -> None:
    """Thả model khỏi bộ nhớ (dùng khi đổi cấu hình, và trong test)."""
    global _model
    _model = None


def _probability(logprob: float | None) -> float:
    """Whisper trả log-probability; quy về xác suất 0..1 cho dễ đặt ngưỡng.

    `word.probability` của faster-whisper đã là xác suất, nhưng ta phòng trường
    hợp chỉ có avg_logprob ở mức segment.
    """
    if logprob is None:
        return 0.0
    if 0.0 <= logprob <= 1.0:
        return float(logprob)
    return float(max(0.0, min(1.0, math.exp(logprob))))


class WhisperEngine:
    """Cài đặt `AsrEngine` bằng faster-whisper."""

    name = "faster-whisper"

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        model = _load_model()
        settings = speaking_settings()

        try:
            segments, info = model.transcribe(
                audio_path,
                language=language or settings.default_language,
                # BẮT BUỘC: toàn bộ đặc trưng fluency dựa vào mốc thời gian từng từ
                word_timestamps=True,
                vad_filter=settings.vad_filter,
                beam_size=settings.beam_size,
            )
            segments = list(segments)
        except Exception as exc:                       # noqa: BLE001
            raise AsrUnavailable(f"Whisper không xử lý được file audio: {exc}") from exc

        words: list[Word] = []
        no_speech: list[float] = []

        for segment in segments:
            no_speech.append(float(getattr(segment, "no_speech_prob", 0.0) or 0.0))
            segment_words = getattr(segment, "words", None) or []

            for word in segment_words:
                text = (word.word or "").strip()
                if not text:
                    continue
                words.append(Word(
                    text=text,
                    start=float(word.start),
                    end=float(word.end),
                    confidence=_probability(getattr(word, "probability", None)),
                ))

        # Thời lượng: ưu tiên metadata của file, ngược lại lấy mốc kết thúc cuối
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if duration <= 0 and words:
            duration = words[-1].end

        return Transcript(
            text=" ".join(w.text for w in words).strip(),
            words=words,
            duration_sec=duration,
            language=getattr(info, "language", language or settings.default_language),
            no_speech_prob=(sum(no_speech) / len(no_speech)) if no_speech else 0.0,
        )
