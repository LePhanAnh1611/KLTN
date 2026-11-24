"""Client gọi LLM để chấm bài viết (UC-37).

Hệ thống KHÔNG bắt buộc phải có LLM. Cùng tinh thần degrade mềm của `dkt_client`
(UC-64 E2): thiếu API key, mạng lỗi hay hết hạn mức thì trả None để caller rơi
về bộ chấm heuristic, thay vì chặn người học không nộp được bài.

Vì sao có bộ chấm dự phòng thay vì báo lỗi: bài luyện viết là [C] trong danh mục
nghiệp vụ, không phải lõi khoa học của khóa luận. Người chấm là ai thì trả về
trong `grader` để giao diện nói thật với người học — không bao giờ trình bày
nhận xét máy móc như thể là nhận xét của AI.
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=3.0, read=25.0, write=10.0, pool=3.0)
COOLDOWN_SECONDS = 60.0

_disabled_until: float = 0.0

_SYSTEM_PROMPT = (
    "Bạn là giáo viên tiếng Anh chấm bài dịch Việt→Anh cho người học Việt Nam. "
    "Trả về DUY NHẤT một JSON object với các khóa: "
    '"score" (số nguyên 0-100), '
    '"feedback" (nhận xét ngắn bằng TIẾNG VIỆT, chỉ rõ lỗi ngữ pháp/từ vựng), '
    '"suggestion" (một bản dịch tốt bằng tiếng Anh). '
    "Không thêm chữ nào ngoài JSON."
)


def reset_circuit() -> None:
    """Cho phép gọi lại ngay (dùng trong test)."""
    global _disabled_until
    _disabled_until = 0.0


def _groq_configured() -> bool:
    """Có GROQ_API_KEY (cùng key với module luyện nói / hội thoại AI)."""
    from app.speaking.config import speaking_settings

    return bool(speaking_settings().groq_api_key)


def is_configured() -> bool:
    """Có ít nhất một LLM để chấm: Anthropic (LLM_API_KEY) hoặc Groq (GROQ_API_KEY).

    Bản pilot chỉ cấu hình Groq. Trước đây hàm này chỉ nhìn `llm_api_key` nên mọi
    bài viết trên pilot đều lặng lẽ rơi về heuristic dù key Groq vẫn có.
    """
    return bool(getattr(settings, "llm_api_key", None)) or _groq_configured()


def _call_anthropic(prompt_vi: str, answer_en: str) -> dict:
    payload = {
        "model": settings.llm_model,
        "max_tokens": 600,
        "system": _SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": f"Câu tiếng Việt: {prompt_vi}\nBài làm của học viên: {answer_en}",
        }],
    }
    response = httpx.post(
        f"{settings.llm_base_url}/v1/messages",
        headers={
            "x-api-key": settings.llm_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return json.loads(response.json()["content"][0]["text"])


def _call_groq(prompt_vi: str, answer_en: str) -> dict:
    # Import muộn: tránh vòng import (ollama_client không phụ thuộc module này).
    from app.speaking.scoring import ollama_client

    return ollama_client.chat_json(
        _SYSTEM_PROMPT,
        f"Câu tiếng Việt: {prompt_vi}\nBài làm của học viên: {answer_en}",
        temperature=0.1,
    )


def grade_writing(prompt_vi: str, answer_en: str) -> dict | None:
    """Chấm một bài dịch. Trả None nghĩa là LLM không dùng được lúc này.

    Ưu tiên Anthropic nếu có `LLM_API_KEY`, không thì Groq (`GROQ_API_KEY`).
    """
    global _disabled_until

    if not is_configured():
        return None
    if time.monotonic() < _disabled_until:
        return None

    try:
        if getattr(settings, "llm_api_key", None):
            parsed = _call_anthropic(prompt_vi, answer_en)
        else:
            parsed = _call_groq(prompt_vi, answer_en)
    except Exception as exc:                      # noqa: BLE001 — degrade mềm có chủ đích
        logger.warning("LLM không dùng được, rơi về bộ chấm heuristic: %s", exc)
        _disabled_until = time.monotonic() + COOLDOWN_SECONDS
        return None

    if not isinstance(parsed, dict):
        logger.warning("LLM trả về không phải JSON object: %r", type(parsed))
        return None

    score = parsed.get("score")
    if not isinstance(score, (int, float)):
        logger.warning("LLM trả về score không hợp lệ: %r", score)
        return None

    return {
        "score": max(0.0, min(100.0, float(score))),
        "feedback": str(parsed.get("feedback") or "").strip() or None,
        "suggestion": str(parsed.get("suggestion") or "").strip() or None,
    }
