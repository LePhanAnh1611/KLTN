"""Sinh `developmental_feedback` — đoạn nhận xét hành động được cho người học.

Rubric mục 6: đầu ra nên gồm mức từng tiêu chí + 1-2 bằng chứng cụ thể + gợi ý
cải thiện ƯU TIÊN NHẤT. Chữ "ưu tiên nhất" là mấu chốt: liệt kê cả bốn gợi ý
cùng lúc thì người tự học không biết bắt đầu từ đâu.

Có LLM thì nhờ nó viết cho mượt; không có thì ghép từ chính rubric. Bản ghép
luôn dùng được và không bịa gì — nó chỉ trích lại descriptor + gợi ý đã có sẵn.
"""
from __future__ import annotations

import logging

from app.speaking.rubric import CRITERIA, Rubric
from app.speaking.scoring.aggregate import summary_line
from app.speaking.scoring.ollama_client import OllamaUnavailable, chat_json
from app.speaking.types import CriterionScore

logger = logging.getLogger(__name__)

CRITERION_NAMES = {
    "fluency": "độ trôi chảy",
    "pronunciation": "độ dễ hiểu",
    "grammar_vocab": "ngữ pháp & từ vựng",
    "coherence_task": "mạch lạc & bám đề",
}

_SYSTEM = (
    "Bạn là huấn luyện viên ngoại ngữ viết nhận xét cho người TỰ HỌC (không có "
    "giáo viên kèm). Viết bằng tiếng Việt, giọng thẳng thắn và khích lệ, "
    "3-5 câu. Chỉ dựa trên dữ liệu được cung cấp, KHÔNG bịa thêm chi tiết về "
    "bài nói. Nêu đúng MỘT việc nên làm tiếp theo. "
    'Trả DUY NHẤT JSON dạng {"feedback": "..."}.'
)


def _weakest(scores: dict[str, CriterionScore]) -> CriterionScore | None:
    """Tiêu chí yếu nhất trong số các tiêu chí THỰC SỰ chấm được."""
    usable = [s for s in scores.values() if s.scored_by != "fallback"]
    if not usable:
        return None
    # Hòa thì ưu tiên theo thứ tự rubric (C1 trước C4): nền tảng trước, tinh chỉnh sau
    order = {key: i for i, key in enumerate(CRITERIA)}
    return min(usable, key=lambda s: (s.level, order.get(s.criterion, 99)))


def compose_rule_based(
    scores: dict[str, CriterionScore], rubric: Rubric, overall: int,
) -> str:
    """Bản ghép từ rubric — luôn chạy được, không cần LLM."""
    lines = [summary_line(scores, rubric.labels)]

    weakest = _weakest(scores)
    if weakest is not None:
        name = CRITERION_NAMES.get(weakest.criterion, weakest.criterion)
        lines.append(f"Điểm cần ưu tiên nhất lúc này là {name}.")
        if weakest.evidence:
            lines.append(f"Căn cứ: {weakest.evidence[0]}")
        lines.append(f"Việc nên làm tiếp theo: {weakest.suggestion}")

    strongest = max(
        (s for s in scores.values() if s.scored_by != "fallback"),
        key=lambda s: s.level, default=None,
    )
    if strongest is not None and weakest is not None and strongest.level > weakest.level:
        lines.append(
            f"Điểm đang tốt: {CRITERION_NAMES.get(strongest.criterion)} "
            f"đã ở mức {strongest.label} - giữ nhịp này."
        )

    skipped = [s for s in scores.values() if s.scored_by == "fallback"]
    if skipped:
        names = ", ".join(CRITERION_NAMES.get(s.criterion, s.criterion) for s in skipped)
        lines.append(f"(Chưa chấm được: {names}.)")

    return " ".join(lines)


def compose(
    scores: dict[str, CriterionScore],
    rubric: Rubric,
    overall: int,
    *,
    use_llm: bool = True,
) -> str:
    """Nhận xét tổng hợp. LLM lỗi -> tự động dùng bản ghép từ rubric."""
    baseline = compose_rule_based(scores, rubric, overall)
    if not use_llm:
        return baseline

    facts: list[str] = []
    for key in CRITERIA:
        score = scores.get(key)
        if score is None or score.scored_by == "fallback":
            continue
        evidence = " | ".join(score.evidence[:2]) or "không có trích dẫn"
        facts.append(
            f"- {CRITERION_NAMES[key]}: mức {score.level} ({score.label}). "
            f"Bằng chứng: {evidence}. Gợi ý rubric: {score.suggestion}"
        )

    if not facts:
        return baseline

    weakest = _weakest(scores)
    user = "\n".join([
        "KẾT QUẢ CHẤM:",
        *facts,
        "",
        f"Mức chung: {overall} ({rubric.label_of(overall)}).",
        f"Tiêu chí yếu nhất: {CRITERION_NAMES.get(weakest.criterion) if weakest else 'không rõ'}.",
        "",
        "Viết nhận xét cho người học dựa ĐÚNG trên các dữ kiện trên.",
    ])

    try:
        payload = chat_json(_SYSTEM, user, temperature=0.3)
    except OllamaUnavailable as exc:
        logger.info("Không sinh được nhận xét bằng LLM, dùng bản ghép rubric: %s", exc)
        return baseline

    text = str(payload.get("feedback") or "").strip()
    return text or baseline
