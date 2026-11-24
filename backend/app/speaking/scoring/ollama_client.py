"""Client LLM dùng chung — nay gọi **Groq Cloud**, không còn Ollama local.

Trước đây file này nói chuyện với `localhost:11434`. Đổi sang Groq (API tương
thích OpenAI) để máy chủ không phải nuôi một mô hình 7B: nhanh hơn nhiều và
không ăn CPU/RAM. Đây vẫn là client LLM DUY NHẤT cho ba luồng — chấm C3/C4 của
module luyện nói, gắn chủ đề PDF (UC-87), hội thoại roleplay (UC-39) — nên đổi
ở đây là đổi cho cả ba.

Tên module, tên hàm và tên exception (`OllamaUnavailable`) GIỮ NGUYÊN có chủ ý:
`llm_scorer`, `pdf_import.topic`, `conversation_service` và các test đều bắt
đúng những tên này. Đổi tên là phải sửa lan man và làm hỏng đường degrade đã
kiểm thử. Coi "Ollama" ở đây là "nhà cung cấp LLM", không phải sản phẩm cụ thể.

Khác `app.services.llm_client` (gọi Anthropic cho UC-37): file này giữ riêng vì
hai luồng có ràng buộc cấu hình và đường lùi khác nhau.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.speaking.config import speaking_settings

logger = logging.getLogger(__name__)


class OllamaUnavailable(RuntimeError):
    """LLM không dùng được. Caller quyết định degrade thế nào."""


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def is_available() -> bool:
    """Ping nhanh — dùng cho health check, KHÔNG dùng trước mỗi lần chấm.

    Thiếu API key thì trả False ngay, không tốn một vòng mạng: đó là dạng
    "không sẵn sàng" phổ biến nhất khi mới clone repo về.
    """
    settings = speaking_settings()
    if not settings.groq_api_key:
        return False
    try:
        response = httpx.get(
            f"{settings.groq_base_url}/models",
            headers=_headers(settings.groq_api_key),
            timeout=5.0,
        )
        response.raise_for_status()
        return True
    except Exception:                                  # noqa: BLE001
        return False


def installed_models() -> list[str]:
    """Danh sách model Groq cho phép key này dùng (tên giữ từ thời Ollama)."""
    settings = speaking_settings()
    if not settings.groq_api_key:
        return []
    try:
        response = httpx.get(
            f"{settings.groq_base_url}/models",
            headers=_headers(settings.groq_api_key),
            timeout=10.0,
        )
        response.raise_for_status()
        return [m["id"] for m in response.json().get("data", [])]
    except Exception:                                  # noqa: BLE001
        return []


def chat_json(system: str, user: str, *, temperature: float | None = None) -> dict:
    """Gọi Groq và bắt buộc trả JSON object.

    Dùng `response_format={"type": "json_object"}` thay vì chỉ dặn trong prompt:
    mô hình rất hay kèm lời dẫn ngoài JSON, và ta không muốn viết bộ dò dấu
    ngoặc. Mọi lỗi mạng/API/parse đều quy về `OllamaUnavailable` để ba caller
    dùng chung một đường lùi.
    """
    settings = speaking_settings()
    if not settings.groq_api_key:
        raise OllamaUnavailable(
            "Thiếu GROQ_API_KEY - đặt biến này trong .env để bật chấm/sinh bằng LLM."
        )

    payload = {
        "model": settings.groq_model,
        "temperature": (
            settings.ollama_temperature if temperature is None else temperature
        ),
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    try:
        response = httpx.post(
            f"{settings.groq_base_url}/chat/completions",
            headers=_headers(settings.groq_api_key),
            json=payload,
            timeout=settings.ollama_timeout_sec,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except Exception as exc:                           # noqa: BLE001
        raise OllamaUnavailable(
            f"Không gọi được Groq tại {settings.groq_base_url} "
            f"(model {settings.groq_model}): {exc}"
        ) from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OllamaUnavailable(f"LLM trả về không phải JSON: {content[:200]!r}") from exc

    if not isinstance(parsed, dict):
        raise OllamaUnavailable(f"LLM trả về JSON không phải object: {type(parsed)}")
    return parsed
