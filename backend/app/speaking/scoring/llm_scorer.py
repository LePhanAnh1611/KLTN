"""Chấm C3 Grammar & Vocabulary và C4 Coherence & Task bằng Ollama.

Bám sát rubric mục 7 — bốn kỹ thuật giữ LLM nhất quán, cài đặt cụ thể:
1. Chấm TỪNG tiêu chí một lần gọi riêng  -> `score_criterion` chỉ nhận 1 tiêu chí.
2. Evidence-first                        -> schema JSON bắt `evidence` TRƯỚC `level`,
                                            và prompt nói rõ phải trích dẫn rồi mới gán mức.
3. Few-shot anchors                      -> `_anchor_block` nhét 4 ví dụ mẫu vào prompt.
4. Nhiệt độ thấp                         -> lấy từ cấu hình (mặc định 0.1).
5. Trung vị nhiều lần chạy (tùy chọn)    -> `SPEAKING_LLM_SAMPLES > 1`.
6. Trả cả mức lẫn lý do                  -> `CriterionScore.reason`.

Thứ tự khóa trong JSON là CÓ CHỦ ĐÍCH: mô hình sinh tuần tự, viết bằng chứng ra
trước buộc nó phải "đọc" transcript rồi mới kết luận, thay vì đoán mức rồi bịa
bằng chứng cho khớp.
"""
from __future__ import annotations

import logging
import re
import statistics

from app.speaking.rubric import Rubric
from app.speaking.rubric.anchors import ANCHORS_BY_CRITERION
from app.speaking.scoring.ollama_client import OllamaUnavailable, chat_json
from app.speaking.config import speaking_settings
from app.speaking.types import CriterionScore

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Bạn là giám khảo chấm bài nói ngoại ngữ. Bạn chấm ĐÚNG MỘT tiêu chí mỗi lần, "
    "theo đúng thang mô tả được cung cấp. "
    "Luôn trả về DUY NHẤT một JSON object, không thêm chữ nào bên ngoài. "
    "Bằng chứng phải TRÍCH NGUYÊN VĂN từ bài nói, không được bịa. "
    "Nếu bài nói quá ngắn để kết luận, hãy chấm mức 1 và nói rõ lý do. "
    # Đặt ở system prompt vì để cuối user prompt thì mô hình đa ngữ (qwen2.5) bỏ
    # qua và trôi sang tiếng Trung giữa chừng — đã gặp thật khi chạy thử.
    "TRƯỜNG reason PHẢI viết hoàn toàn bằng TIẾNG VIỆT. "
    "TUYỆT ĐỐI KHÔNG dùng chữ Hán, chữ Nhật hay bất kỳ hệ chữ nào khác."
)

# Ngưỡng nhận diện "bằng chứng" thực chất là chép cả bài: quá dài thì không còn
# là trích dẫn, và mất hết tác dụng chỉ đúng chỗ cho người học.
MAX_EVIDENCE_WORDS = 25

# Chữ Hán / Kana — dấu hiệu mô hình đa ngữ trôi khỏi tiếng Việt
_NON_LATIN = re.compile(r"[一-鿿぀-ヿ]")

# Thà nói thẳng là không có lời giải thích còn hơn hiện một đoạn người học không
# đọc được — mức vẫn giữ vì con số không phụ thuộc ngôn ngữ diễn đạt.
_WRONG_SCRIPT_NOTE = (
    "Mô hình đã trả lời giải thích bằng ngôn ngữ khác nên phần này bị lược bỏ. "
    "Mức chấm vẫn dựa trên bài nói của bạn."
)


def _rubric_block(rubric: Rubric, criterion: str) -> str:
    spec = rubric.criteria[criterion]
    lines = [f"TIÊU CHÍ {spec.code} — {spec.name}", ""]
    for level in (1, 2, 3, 4):
        descriptor = spec.at(level)
        lines.append(f"Mức {level} ({descriptor.label}): {descriptor.descriptor}")
    return "\n".join(lines)


def _anchor_block(criterion: str) -> str:
    anchors = ANCHORS_BY_CRITERION.get(criterion, [])
    if not anchors:
        return ""

    lines = ["VÍ DỤ MẪU ĐÃ CHẤM (dùng để neo thang điểm):", ""]
    for anchor in anchors:
        if anchor.task:
            lines.append(f'- Đề: "{anchor.task}"')
        lines.append(f'  Bài nói: "{anchor.transcript}"')
        lines.append(f"  → Mức {anchor.level}. Lý do: {anchor.reason}")
        lines.append("")
    return "\n".join(lines)


def _user_prompt(rubric: Rubric, criterion: str, transcript: str, task: str) -> str:
    parts = [_rubric_block(rubric, criterion), ""]

    anchors = _anchor_block(criterion)
    if anchors:
        parts += [anchors, ""]

    if criterion == "coherence_task":
        # C4 phải có đề bài mới xét được "bám đề" (rubric mục 5)
        parts.append(f'ĐỀ BÀI: "{task}"')
        parts.append("")

    parts += [
        "BÀI NÓI CẦN CHẤM (bản gỡ băng, có thể có lỗi nhận dạng):",
        f'"{transcript}"',
        "",
        "Làm theo ĐÚNG thứ tự sau:",
        f"1. Trích 1-3 đoạn NGUYÊN VĂN từ bài nói làm bằng chứng cho tiêu chí này. "
        f"Mỗi đoạn NGẮN (tối đa {MAX_EVIDENCE_WORDS} từ) và là một phần của bài nói, "
        "KHÔNG chép lại toàn bộ bài.",
        "2. Dựa trên bằng chứng đó, chọn mức 1-4 khớp mô tả nhất.",
        "3. Giải thích ngắn gọn vì sao chọn mức đó chứ không phải mức liền kề.",
        "",
        "Trả JSON đúng dạng (giữ nguyên thứ tự khóa):",
        '{"evidence": ["...", "..."], "level": 1, "reason": "..."}',
        "Trường evidence và reason viết bằng TIẾNG VIỆT, riêng đoạn trích giữ nguyên gốc.",
    ]
    return "\n".join(parts)


def _parse(payload: dict) -> tuple[int, list[str], str]:
    raw_level = payload.get("level")
    try:
        level = int(raw_level)
    except (TypeError, ValueError):
        raise OllamaUnavailable(f"LLM trả level không hợp lệ: {raw_level!r}")
    level = max(1, min(4, level))

    evidence = payload.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    evidence = [_trim_quote(str(e)) for e in evidence if str(e).strip()][:3]

    return level, evidence, str(payload.get("reason") or "").strip()


def _trim_quote(text: str) -> str:
    """Cắt bằng chứng dài quá thành trích dẫn thật sự.

    Mô hình hay chép nguyên bài nói vào `evidence` (đã gặp khi chạy thử), làm
    mất hẳn giá trị "chỉ đúng chỗ" của bằng chứng.
    """
    words = text.strip().split()
    if len(words) <= MAX_EVIDENCE_WORDS:
        return " ".join(words)
    return " ".join(words[:MAX_EVIDENCE_WORDS]) + "…"


def _has_wrong_script(text: str) -> bool:
    """True nếu lời giải thích trôi sang chữ Hán/Nhật."""
    return bool(_NON_LATIN.search(text))


def _fallback(rubric: Rubric, criterion: str, error: str) -> CriterionScore:
    """LLM không dùng được.

    KHÔNG đoán mức: trả mức 1 kèm lời giải thích trung thực rằng đây không phải
    kết quả chấm. Gán đại một mức "trung bình" sẽ là bịa điểm, và người tự học
    không có giáo viên nào để đối chứng lại (rubric mục 9).
    """
    return CriterionScore(
        criterion=criterion,
        level=1,
        label=rubric.criteria[criterion].at(1).label,
        evidence=[],
        suggestion=rubric.criteria[criterion].at(1).suggestion,
        scored_by="fallback",
        reason=(
            "Chưa chấm được tiêu chí này vì mô hình ngôn ngữ cục bộ không sẵn sàng "
            f"({error}). Mức hiển thị KHÔNG phản ánh bài nói."
        ),
    )


def score_criterion(
    rubric: Rubric, criterion: str, transcript: str, task: str = "",
) -> CriterionScore:
    """Chấm một tiêu chí (grammar_vocab | coherence_task)."""
    settings = speaking_settings()
    system, user = _SYSTEM, _user_prompt(rubric, criterion, transcript, task)

    levels: list[int] = []
    best: tuple[list[str], str] | None = None
    last_error = ""

    # +1 lượt dự phòng cho trường hợp mô hình đa ngữ trôi sang chữ Hán (đã gặp
    # thật với qwen2.5): mức thì vẫn dùng được, nhưng lời giải thích người học
    # không đọc nổi.
    for attempt in range(settings.llm_samples + 1):
        # Dừng khi ĐỦ mẫu VÀ đã có lời giải thích đọc được. Lượt dự phòng chỉ
        # dùng khi lượt trước trôi sang chữ Hán — nếu tính nó vào ngân sách mẫu
        # thì vòng lặp thoát ngay và việc thử lại không bao giờ xảy ra.
        have_readable = best is not None and best[1] != _WRONG_SCRIPT_NOTE
        if len(levels) >= settings.llm_samples and have_readable:
            break

        try:
            level, evidence, reason = _parse(chat_json(system, user))
        except OllamaUnavailable as exc:
            last_error = str(exc)
            logger.warning("Chấm %s lần %d thất bại: %s", criterion, attempt + 1, exc)
            continue

        # Mức vẫn hợp lệ kể cả khi lời giải thích sai ngôn ngữ — con số không
        # phụ thuộc vào việc mô hình diễn đạt bằng thứ tiếng nào.
        if len(levels) < settings.llm_samples:
            levels.append(level)

        if _has_wrong_script(reason):
            logger.warning(
                "Chấm %s lần %d: lời giải thích lẫn chữ Hán/Nhật, thử lại.",
                criterion, attempt + 1,
            )
            if best is None:
                best = (evidence, _WRONG_SCRIPT_NOTE)
            continue

        # Lời giải thích ĐÚNG ngôn ngữ luôn thay thế bản dự phòng
        if best is None or best[1] == _WRONG_SCRIPT_NOTE:
            best = (evidence, reason)

    if not levels or best is None:
        return _fallback(rubric, criterion, last_error or "không rõ nguyên nhân")

    # Rubric mục 7.5 — trung vị nhiều lần chạy. Số chẵn thì làm tròn XUỐNG:
    # nghi ngờ giữa hai mức thì báo mức thấp hơn, để lời khuyên không hụt.
    level = int(statistics.median_low(levels))
    evidence, reason = best

    if len(levels) > 1:
        reason = f"{reason} (trung vị của {len(levels)} lần chấm: {levels})".strip()

    descriptor = rubric.criteria[criterion].at(level)
    return CriterionScore(
        criterion=criterion,
        level=level,
        label=descriptor.label,
        evidence=evidence,
        suggestion=descriptor.suggestion,
        scored_by="llm",
        reason=reason,
    )
