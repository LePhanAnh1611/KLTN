"""Few-shot anchor examples — rubric mục 7.3 ("neo" thang điểm cho LLM).

Chỉ cần cho C3 và C4 vì đó là hai tiêu chí do LLM chấm; C1/C2 quy từ số đo nên
không có chỗ để trôi.

Mỗi anchor là một transcript ngắn KÈM mức đúng và lý do. Cố ý viết transcript
bằng tiếng Anh (giống bài nói thật) còn lý do bằng tiếng Việt (giống đúng định
dạng đầu ra ta muốn LLM bắt chước).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    transcript: str
    level: int
    reason: str
    task: str = ""


GRAMMAR_VOCAB_ANCHORS: list[Anchor] = [
    Anchor(
        transcript="I go school yesterday. Is very fun. I like.",
        level=1,
        reason="Sai thì cơ bản (go/went), thiếu chủ ngữ và mạo từ, câu cụt, vốn từ rất hẹp.",
    ),
    Anchor(
        transcript=(
            "Yesterday I went to the museum with my friend. It was interesting "
            "because we saw many old things. But I don't know how to say some words."
        ),
        level=2,
        reason=(
            "Câu cơ bản đúng, có liên từ; nhưng chỉ dừng ở cấu trúc đơn giản và "
            "vốn từ chung chung ('many old things')."
        ),
    ),
    Anchor(
        transcript=(
            "Last weekend I visited the history museum, which I had been meaning to "
            "do for a while. What struck me most was the collection of ancient "
            "pottery — some pieces were over two thousand years old."
        ),
        level=3,
        reason=(
            "Mệnh đề quan hệ và thì quá khứ hoàn thành dùng đúng; vốn từ cụ thể "
            "('collection', 'pottery'); lỗi nếu có thì lẻ tẻ."
        ),
    ),
    Anchor(
        transcript=(
            "Had I known how extensive the exhibition was, I would have set aside "
            "the whole afternoon. What I found compelling wasn't the artefacts "
            "themselves so much as the curatorial narrative threading them together."
        ),
        level=4,
        reason=(
            "Đảo ngữ điều kiện, cấu trúc nhấn mạnh 'what...was', collocation chính "
            "xác về sắc thái; gần như không lỗi."
        ),
    ),
]

COHERENCE_TASK_ANCHORS: list[Anchor] = [
    Anchor(
        task="Describe a place you enjoy visiting and explain why.",
        transcript="I like food. Pizza is good. My friend also.",
        level=1,
        reason="Không trả lời đề (không nêu địa điểm), ý rời rạc, quá ngắn.",
    ),
    Anchor(
        task="Describe a place you enjoy visiting and explain why.",
        transcript=(
            "I like the beach. It is nice. There is water and sand. I go with my "
            "family. We eat food there. It is fun."
        ),
        level=2,
        reason=(
            "Có trả lời đề nhưng ý rời, gần như không từ nối; vế 'why' mới dừng ở "
            "'it is fun' chứ chưa phát triển."
        ),
    ),
    Anchor(
        task="Describe a place you enjoy visiting and explain why.",
        transcript=(
            "The place I enjoy most is a small bookshop near my university. "
            "Firstly, it's quiet, so I can actually concentrate there. Secondly, "
            "the owner recommends books I would never have picked myself. That's "
            "why I keep going back every weekend."
        ),
        level=3,
        reason=(
            "Bám sát cả hai vế của đề (nơi nào + vì sao), từ nối rõ ràng, mỗi lý do "
            "được phát triển bằng một câu giải thích."
        ),
    ),
    Anchor(
        task="Describe a place you enjoy visiting and explain why.",
        transcript=(
            "If I had to pick one place, it would be a second-hand bookshop near "
            "campus — though the appeal has less to do with the books than with "
            "what the place does to my attention. In a city this loud, an hour "
            "there resets something. And because the owner curates by instinct "
            "rather than by sales rank, I leave with things I'd never have searched "
            "for. That combination — quiet plus serendipity — is what keeps me "
            "coming back."
        ),
        level=4,
        reason=(
            "Lập luận có tuyến rõ ràng, liên kết mượt bằng cấu trúc chứ không chỉ "
            "từ nối rời; phát triển ý sâu và kết lại đúng trọng tâm đề."
        ),
    ),
]

ANCHORS_BY_CRITERION: dict[str, list[Anchor]] = {
    "grammar_vocab": GRAMMAR_VOCAB_ANCHORS,
    "coherence_task": COHERENCE_TASK_ANCHORS,
}
