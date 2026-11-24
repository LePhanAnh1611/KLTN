"""Tổng hợp mức 4 tiêu chí thành mức chung — rubric mục 6.

Quy tắc: trung bình có trọng số, làm tròn về mức gần nhất. Trọng số mặc định
bằng nhau; người gọi ghi đè được (VD người luyện thuyết trình tăng C4).

Đúng 0.5 thì làm tròn XUỐNG, giống cách `llm_scorer` lấy trung vị dưới: phân vân
giữa hai mức thì báo mức thấp hơn để lời khuyên không bị hụt. KHÔNG dùng `round()`
của Python ở đây — hàm đó làm tròn về số chẵn gần nhất (round(2.5)==2 nhưng
round(1.5)==2), tức cùng một khoảng cách lại ra hai kiểu kết quả khác nhau, không
giải thích được cho người học.
"""
from __future__ import annotations

import math

from app.speaking.rubric import CRITERIA
from app.speaking.rubric.thresholds import load_thresholds
from app.speaking.types import CriterionScore


def default_weights() -> dict[str, float]:
    return dict(load_thresholds()["aggregate"]["default_weights"])


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Bỏ khóa lạ và trọng số âm; thiếu khóa nào thì lấy mặc định."""
    base = default_weights()
    if not weights:
        return base

    merged = dict(base)
    for key, value in weights.items():
        if key in base and value is not None and float(value) >= 0:
            merged[key] = float(value)

    if sum(merged.values()) <= 0:        # tất cả bằng 0 -> vô nghĩa, quay về mặc định
        return base
    return merged


def _round_half_down(value: float) -> int:
    """Làm tròn về số nguyên gần nhất; đúng 0.5 thì xuống."""
    return math.ceil(value - 0.5)


def overall_level(
    scores: dict[str, CriterionScore], weights: dict[str, float] | None = None,
) -> int:
    """Mức chung 1..4.

    Tiêu chí `scored_by == 'fallback'` bị LOẠI khỏi phép tính: mức 1 ở đó nghĩa
    là "chưa chấm được", không phải "người học yếu". Gộp vào sẽ kéo mức chung
    xuống oan. Nếu không còn tiêu chí nào chấm được thì trả 1.
    """
    usable = {
        key: score for key, score in scores.items()
        if key in CRITERIA and score.scored_by != "fallback"
    }
    if not usable:
        return 1

    resolved = normalize_weights(weights)
    total_weight = sum(resolved[key] for key in usable)
    if total_weight <= 0:
        return 1

    weighted = sum(usable[key].level * resolved[key] for key in usable) / total_weight
    return max(1, min(4, _round_half_down(weighted)))


def summary_line(scores: dict[str, CriterionScore], labels: dict[int, str]) -> str:
    """Mô tả dạng chữ theo gợi ý rubric mục 6.

    Gom các tiêu chí cùng mức lại: "Developing về Fluency, Proficient về phần
    còn lại" đọc dễ hơn là liệt kê bốn dòng giống nhau.
    """
    names = {
        "fluency": "Độ trôi chảy",
        "pronunciation": "Độ dễ hiểu",
        "grammar_vocab": "Ngữ pháp & từ vựng",
        "coherence_task": "Mạch lạc & bám đề",
    }

    by_level: dict[int, list[str]] = {}
    for key in CRITERIA:
        score = scores.get(key)
        if score is None or score.scored_by == "fallback":
            continue
        by_level.setdefault(score.level, []).append(names[key])

    if not by_level:
        return "Chưa chấm được tiêu chí nào."

    parts = [
        f"{labels.get(level, level)} về {', '.join(items)}"
        for level, items in sorted(by_level.items(), reverse=True)
    ]
    return "; ".join(parts) + "."
