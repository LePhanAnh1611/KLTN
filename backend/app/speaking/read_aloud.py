"""Chấm ĐỌC THEO CÂU MẪU — luyện nói câu chứa từ vựng đang học.

Khác `pipeline.assess` (nói tự do theo đề IELTS) ở ba điểm, và cả ba đều là hệ
quả của việc BIẾT TRƯỚC câu cần đọc:

1. KHÔNG gọi LLM. Ngữ pháp và bố cục ý nằm sẵn trong câu mẫu — người học không
   sáng tác gì để mà chấm. Bỏ LLM đưa thời gian từ ~106s xuống ~2s, đủ nhanh để
   luyện liên tục từng câu một.
2. Có độ chính xác THẬT (từ nào đúng/sai/thiếu) thay vì chỉ suy gián tiếp từ độ
   tin cậy ASR.
3. Dùng ba khía cạnh riêng, KHÔNG mượn rubric 4 tiêu chí: C3 (ngữ pháp & từ
   vựng) và C4 (mạch lạc & bám đề) của rubric đó giả định người học tự tạo lời.
   Đọc lại câu cho sẵn thì hai tiêu chí ấy vô nghĩa — chấm chúng là chấm bịa.

Vẫn giữ thang 4 mức và nhãn Emerging/Developing/Proficient/Advanced cho nhất
quán với phần còn lại của sản phẩm.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.speaking.asr.base import AsrEngine
from app.speaking.features import fluency as fluency_features
from app.speaking.features.accuracy import ReadAloudAccuracy, compare
from app.speaking.rubric.thresholds import is_calibrated, load_thresholds
from app.speaking.types import Transcript

LEVEL_LABELS = {1: "Emerging", 2: "Developing", 3: "Proficient", 4: "Advanced"}

# Ngưỡng cho chế độ đọc câu. Để ở đây (không nhét vào thresholds.json của rubric
# nói tự do) vì đây là thang khác, calibrate riêng.
ACCURACY_BANDS = {4: 0.95, 3: 0.8, 2: 0.6}
CLARITY_BANDS = {4: 0.9, 3: 0.78, 2: 0.6}

# Dưới mức này thì bản ghi không đủ để kết luận
MIN_WORDS = 2


@dataclass(frozen=True)
class AspectScore:
    key: str
    label: str
    level: int
    level_label: str
    detail: str
    suggestion: str


@dataclass(frozen=True)
class ReadAloudResult:
    item_id: int
    word: str
    expected_text: str
    transcript: str

    accuracy: float                 # 0..1
    clarity: float                  # 0..1 (độ tin cậy ASR trung bình)
    overall_level: int
    aspects: list[AspectScore]

    words: list[dict]               # từng từ: expected / heard / ok / confidence
    missed_words: list[str]
    extra_words: list[str]

    audio_metrics: dict
    feedback: str
    warnings: list[str] = field(default_factory=list)


def _level_from(value: float, bands: dict[int, float]) -> int:
    for level in (4, 3, 2):
        if value >= bands[level]:
            return level
    return 1


def _accuracy_aspect(result: ReadAloudAccuracy) -> AspectScore:
    level = _level_from(result.accuracy, ACCURACY_BANDS)

    if result.missed_words:
        listed = ", ".join(f"“{w}”" for w in result.missed_words[:5])
        detail = (
            f"Đọc đúng {result.correct_count}/{result.expected_count} từ. "
            f"Chưa khớp: {listed}."
        )
        suggestion = (
            f"Nghe lại câu mẫu rồi đọc chậm phần có {result.missed_words[0]!r}, "
            "sau đó mới đọc trọn câu."
        )
    else:
        detail = f"Đọc đúng trọn vẹn cả {result.expected_count} từ."
        suggestion = "Thử đọc nhanh hơn một chút mà vẫn giữ rõ từng từ."

    if result.extra_words:
        detail += f" Có {len(result.extra_words)} từ nói thêm ngoài câu mẫu."

    return AspectScore(
        key="accuracy", label="Đọc đúng câu", level=level,
        level_label=LEVEL_LABELS[level], detail=detail, suggestion=suggestion,
    )


def _clarity_aspect(result: ReadAloudAccuracy, avg_confidence: float) -> AspectScore:
    level = _level_from(avg_confidence, CLARITY_BANDS)

    # Từ ĐÚNG nhưng máy nghe không chắc = phát âm chưa rõ. Đây là thông tin mà
    # chế độ nói tự do không có, vì ở đó không biết đâu là từ đúng.
    unclear = [
        w.expected for w in result.words
        if w.ok and w.confidence is not None and w.confidence < 0.7
    ]

    detail = f"Độ rõ trung bình {avg_confidence:.0%}."
    if unclear:
        detail += " Đọc đúng từ nhưng chưa rõ: " + ", ".join(f"“{w}”" for w in unclear[:5]) + "."
        suggestion = f"Luyện riêng âm của {unclear[0]!r}, đọc chậm và tách rõ âm cuối."
    else:
        detail += " Không có từ nào nghe không rõ."
        suggestion = "Giữ nguyên cách phát âm này; thử thêm ngữ điệu lên/xuống cuối câu."

    return AspectScore(
        key="clarity", label="Độ rõ", level=level,
        level_label=LEVEL_LABELS[level], detail=detail, suggestion=suggestion,
    )


def _fluency_aspect(features) -> AspectScore:
    config = load_thresholds()["fluency"]

    by_speed = 4 if features.words_per_minute >= float(config["words_per_minute"]["3"]) else (
        3 if features.words_per_minute >= float(config["words_per_minute"]["2"]) else 2
    )
    # Đọc một câu ngắn thì một lần dừng dài đã là vấp; ngưỡng chặt hơn nói tự do
    by_pause = 4 if features.pause_count == 0 else (
        3 if features.pause_count <= 1 else (2 if features.pause_count <= 3 else 1)
    )
    level = max(1, min(by_speed, by_pause))

    detail = (
        f"{features.words_per_minute:.0f} từ/phút, "
        f"{features.pause_count} lần ngập ngừng"
        + (f" (dài nhất {features.longest_pause_sec:.1f}s)." if features.pause_count else ".")
    )
    suggestion = (
        "Đọc trọn câu một hơi, không dừng giữa chừng."
        if features.pause_count > 1
        else "Giữ nhịp đều như vậy, thử đọc liền mạch hơn nữa."
    )

    return AspectScore(
        key="fluency", label="Trôi chảy", level=level,
        level_label=LEVEL_LABELS[level], detail=detail, suggestion=suggestion,
    )


def _compose_feedback(aspects: list[AspectScore], overall: int) -> str:
    """Nhận xét ghép từ chính kết quả — không cần LLM, nên không tốn thời gian."""
    weakest = min(aspects, key=lambda a: a.level)
    strongest = max(aspects, key=lambda a: a.level)

    lines = [f"Mức chung: {overall} ({LEVEL_LABELS[overall]})."]
    if weakest.level < strongest.level:
        lines.append(f"Điểm cần sửa trước: {weakest.label.lower()}. {weakest.detail}")
    else:
        lines.append(weakest.detail)
    lines.append(f"Việc nên làm tiếp theo: {weakest.suggestion}")
    return " ".join(lines)


def assess_sentence(
    audio_path: str,
    *,
    item_id: int,
    word: str,
    expected_text: str,
    asr: AsrEngine,
    language: str | None = None,
) -> ReadAloudResult:
    """Chấm một lần đọc câu mẫu. KHÔNG gọi LLM."""
    transcript: Transcript = asr.transcribe(audio_path, language=language)

    accuracy = compare(
        expected_text,
        [w.text for w in transcript.words],
        [w.confidence for w in transcript.words],
    )
    fluency = fluency_features.extract(transcript)

    avg_confidence = (
        sum(w.confidence for w in transcript.words) / len(transcript.words)
        if transcript.words else 0.0
    )

    warnings: list[str] = []
    if transcript.word_count < MIN_WORDS:
        warnings.append(
            "Gần như không nhận ra được lời nói nào. Kiểm tra micro rồi đọc lại."
        )
    if not is_calibrated():
        warnings.append(
            "Thang điểm chưa được đối chiếu với người chấm thật - hãy xem kết quả "
            "như một tham chiếu để luyện, không phải điểm chuẩn."
        )

    aspects = [
        _accuracy_aspect(accuracy),
        _clarity_aspect(accuracy, avg_confidence),
        _fluency_aspect(fluency),
    ]

    # Đọc đúng câu là mục tiêu chính của bài này, nên mức chung KHÔNG được cao
    # hơn mức đọc đúng: đọc sai nửa câu mà vẫn "Advanced" vì giọng rõ là vô lý.
    overall = min(
        round(sum(a.level for a in aspects) / len(aspects)),
        aspects[0].level,
    )
    overall = max(1, min(4, overall))

    return ReadAloudResult(
        item_id=item_id,
        word=word,
        expected_text=accuracy.expected_text,
        transcript=transcript.text,
        accuracy=round(accuracy.accuracy, 4),
        clarity=round(avg_confidence, 4),
        overall_level=overall,
        aspects=aspects,
        words=[
            {
                "expected": w.expected, "heard": w.heard, "ok": w.ok,
                "confidence": round(w.confidence, 4) if w.confidence is not None else None,
            }
            for w in accuracy.words
        ],
        missed_words=accuracy.missed_words,
        extra_words=accuracy.extra_words,
        audio_metrics={
            "duration_sec": fluency.duration_sec,
            "words_per_minute": fluency.words_per_minute,
            "pause_count": fluency.pause_count,
            "longest_pause_sec": fluency.longest_pause_sec,
            "asr_avg_confidence": round(avg_confidence, 4),
            "word_count": transcript.word_count,
        },
        feedback=_compose_feedback(aspects, overall),
        warnings=warnings,
    )
