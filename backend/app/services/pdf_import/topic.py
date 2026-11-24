"""Bước 4 của N1 — gom chủ đề cho từ bằng LLM chạy local.

Dùng lại `app.speaking.scoring.ollama_client` thay vì viết client Ollama thứ
hai: đó là client Ollama duy nhất của hệ thống (`app.services.llm_client` gọi
Anthropic, phục vụ UC-37). Đây là phụ thuộc một chiều — module luyện nói không
biết gì về UC-87, nên tính độc lập của nó vẫn nguyên.

Chủ đề là thông tin **trang trí**: có thì bộ từ gọn gàng hơn, không có thì người
học vẫn tạo được bộ từ. Vì vậy mọi lỗi LLM đều nuốt thành "không có chủ đề" +
một cảnh báo hiện lên giao diện, KHÔNG được làm hỏng cả luồng (BR-PDF-03).
"""
from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

BATCH_SIZE = 25
MAX_TOPIC_LENGTH = 40

_SYSTEM_PROMPT = (
    "Bạn phân loại chủ đề cho từ vựng tiếng Anh. "
    "Với mỗi từ được đưa, gán MỘT chủ đề ngắn bằng TIẾNG VIỆT (2-4 từ), "
    'ví dụ "Kinh doanh", "Sức khỏe", "Công nghệ", "Môi trường". '
    'Trả về DUY NHẤT một JSON object dạng {"topics": {"<từ>": "<chủ đề>"}}. '
    "TUYỆT ĐỐI KHÔNG đoán trình độ CEFR, không thêm chữ nào ngoài JSON."
)


def is_available() -> bool:
    """Ollama có đang chạy không (chỉ dùng cho health check)."""
    from app.speaking.scoring import ollama_client

    return ollama_client.is_available()


def _tag_batch(lemmas: list[str]) -> dict[str, str]:
    from app.speaking.scoring import ollama_client

    parsed = ollama_client.chat_json(
        _SYSTEM_PROMPT,
        "Danh sách từ: " + ", ".join(lemmas),
        temperature=0.0,  # cùng tài liệu, chạy lại phải ra cùng chủ đề
    )
    raw = parsed.get("topics")
    if not isinstance(raw, dict):
        logger.warning("Ollama trả về 'topics' không phải object: %r", type(raw))
        return {}

    known = {lemma.lower(): lemma for lemma in lemmas}
    topics: dict[str, str] = {}
    for key, value in raw.items():
        lemma = known.get(str(key).strip().lower())
        topic = str(value or "").strip()[:MAX_TOPIC_LENGTH]
        if lemma and topic:
            topics[lemma] = topic
    return topics


def tag_topics(lemmas: Iterable[str], *, batch_size: int = BATCH_SIZE) -> dict[str, str]:
    """Gán chủ đề theo lô. Trả về map lemma -> chủ đề; thiếu từ nào là bình thường.

    Lô đầu tiên hỏng thì DỪNG luôn: Ollama chết là chết cho cả tài liệu, chạy
    tiếp 20 lô nữa chỉ để mỗi lô chờ timeout là bắt người học đợi vô ích.
    """
    from app.speaking.scoring.ollama_client import OllamaUnavailable

    items = [lemma for lemma in lemmas if lemma]
    if not items:
        return {}

    topics: dict[str, str] = {}
    for start in range(0, len(items), max(1, batch_size)):
        batch = items[start : start + max(1, batch_size)]
        try:
            topics.update(_tag_batch(batch))
        except OllamaUnavailable as exc:
            logger.warning("Bỏ qua bước gán chủ đề (UC-87): %s", exc)
            break
        except Exception as exc:  # noqa: BLE001 — degrade mềm có chủ đích (BR-PDF-03)
            logger.warning("Lỗi ngoài dự kiến khi gán chủ đề (UC-87): %s", exc)
            break
    return topics
