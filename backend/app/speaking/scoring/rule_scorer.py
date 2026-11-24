"""Chấm C1 Fluency và C2 Intelligibility từ số đo — KHÔNG dùng LLM.

Hai tiêu chí này có tín hiệu định lượng (rubric mục 5), nên đưa qua LLM chỉ tổ
thêm một nguồn dao động. Quy tắc ở đây tất định: cùng một bản ghi luôn ra cùng
một mức.

Cách quy mức: mỗi chỉ số cho ra một mức riêng, rồi lấy MỨC THẤP NHẤT. Người nói
nhanh nhưng dừng liên tục thì độ trôi chảy vẫn kém — lấy trung bình sẽ giấu mất
điểm yếu, mà rubric là công cụ coaching nên phải chỉ đúng chỗ yếu.
"""
from __future__ import annotations

from app.speaking.rubric import Rubric
from app.speaking.rubric.thresholds import load_thresholds
from app.speaking.types import (
    CriterionScore,
    FluencyFeatures,
    PronunciationSignal,
    Transcript,
)


def _level_from_min(value: float, bands: dict) -> int:
    """Chỉ số CÀNG CAO CÀNG TỐT (VD words-per-minute)."""
    for level in (4, 3, 2):
        if value >= float(bands[str(level)]):
            return level
    return 1


def _level_from_max(value: float, bands: dict) -> int:
    """Chỉ số CÀNG THẤP CÀNG TỐT (VD pause ratio, số từ đệm)."""
    for level in (4, 3, 2):
        if value <= float(bands[str(level)]):
            return level
    return 1


def score_fluency(features: FluencyFeatures, rubric: Rubric) -> CriterionScore:
    config = load_thresholds()["fluency"]

    by_speed = _level_from_min(features.words_per_minute, config["words_per_minute"])
    by_pause = _level_from_max(features.pause_ratio, config["pause_ratio_max"])
    by_filler = _level_from_max(
        features.filler_per_100_words, config["filler_per_100_words_max"]
    )

    level = min(by_speed, by_pause, by_filler)

    # Nói quá nhanh cũng là vấn đề trôi chảy (nuốt chữ, người nghe không theo kịp),
    # nhưng ngưỡng tốc độ ở trên chỉ phạt phía chậm.
    too_fast = features.words_per_minute >= float(config["wpm_too_fast"])
    if too_fast:
        level = max(1, level - int(config["wpm_too_fast_penalty"]))

    evidence = [
        f"Tốc độ nói {features.words_per_minute:.0f} từ/phút "
        f"(nói thực {features.speech_sec:.1f}s trong {features.duration_sec:.1f}s).",
        f"Ngắt nghỉ chiếm {features.pause_ratio:.0%} thời lượng, "
        f"{features.pause_count} lần dừng, dài nhất {features.longest_pause_sec:.1f}s.",
    ]
    if features.filler_count:
        evidence.append(
            f"{features.filler_count} từ đệm "
            f"({features.filler_per_100_words:.1f} trên 100 từ)."
        )
    else:
        evidence.append("Không có từ đệm nào.")
    if too_fast:
        evidence.append("Tốc độ vượt ngưỡng dễ nghe - cân nhắc nói chậm lại để rõ ý.")

    # Nêu rõ chỉ số nào kéo mức xuống — đó là thứ người học cần sửa trước.
    # Khi cả ba chỉ số cùng mức thì KHÔNG có cái nào "yếu nhất"; nói vậy sẽ khiến
    # người đạt mức 4 tưởng mình đang bị trừ điểm ở đâu đó.
    signals = [("tốc độ", by_speed), ("ngắt nghỉ", by_pause), ("từ đệm", by_filler)]
    lowest = min(value for _, value in signals)
    limiting = [name for name, value in signals if value == lowest]

    if len(limiting) == len(signals):
        reason = "Cả tốc độ, ngắt nghỉ và từ đệm đều ở cùng một mức."
    else:
        reason = f"Mức bị giới hạn bởi: {', '.join(limiting)}."
    if too_fast:
        reason += " Đã trừ một mức vì tốc độ vượt ngưỡng dễ nghe."

    descriptor = rubric.criteria["fluency"].at(level)
    return CriterionScore(
        criterion="fluency",
        level=level,
        label=descriptor.label,
        evidence=evidence,
        suggestion=descriptor.suggestion,
        scored_by="rule",
        reason=reason,
    )


def score_pronunciation(
    signal: PronunciationSignal, rubric: Rubric, transcript: Transcript,
) -> CriterionScore:
    config = load_thresholds()["intelligibility"]

    by_confidence = _level_from_min(signal.score, config["avg_confidence_min"])
    low_ratio = float(signal.detail.get("low_confidence_ratio", 0.0))
    by_low_ratio = _level_from_max(low_ratio, config["low_confidence_ratio_max"])

    level = min(by_confidence, by_low_ratio)

    evidence = list(signal.evidence)
    if signal.source == "asr_confidence":
        # Nói thẳng giới hạn ngay trong bằng chứng, không giấu xuống chân trang
        evidence.append(
            "Lưu ý: mức này đánh giá ĐỘ DỄ HIỂU suy từ tín hiệu nhận dạng giọng nói, "
            "chưa phải chấm chuẩn âm vị."
        )

    descriptor = rubric.criteria["pronunciation"].at(level)
    return CriterionScore(
        criterion="pronunciation",
        level=level,
        label=descriptor.label,
        evidence=evidence,
        suggestion=descriptor.suggestion,
        scored_by="rule",
        reason=f"Nguồn tín hiệu: {signal.source}.",
    )
