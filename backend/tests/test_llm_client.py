"""UC-37 — chọn đường LLM khi chấm bài viết.

Bản pilot chỉ có GROQ_API_KEY. Trước bản sửa này `llm_client` chỉ nhìn
LLM_API_KEY (Anthropic), nên mọi bài viết trên pilot đều về heuristic.
"""
from __future__ import annotations

from app.core.config import settings
from app.services import llm_client
from app.speaking.config import speaking_settings
from app.speaking.scoring import ollama_client


def _use_keys(monkeypatch, *, anthropic: str | None, groq: str) -> None:
    monkeypatch.setattr(settings, "llm_api_key", anthropic, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", groq)
    speaking_settings.cache_clear()
    llm_client.reset_circuit()


def test_groq_used_when_only_groq_key(monkeypatch):
    _use_keys(monkeypatch, anthropic=None, groq="gsk_test")
    calls = []

    def fake_chat(system, user, *, temperature=None):
        calls.append(user)
        return {"score": 140, "feedback": "Thiếu mạo từ.", "suggestion": "I read a book."}

    monkeypatch.setattr(ollama_client, "chat_json", fake_chat)
    try:
        out = llm_client.grade_writing("Đặt câu với “book”.", "I read book.")
    finally:
        speaking_settings.cache_clear()

    assert calls and "I read book." in calls[0]
    assert out == {"score": 100.0, "feedback": "Thiếu mạo từ.", "suggestion": "I read a book."}


def test_no_key_returns_none(monkeypatch):
    _use_keys(monkeypatch, anthropic=None, groq="")
    try:
        assert llm_client.is_configured() is False
        assert llm_client.grade_writing("x", "y") is None
    finally:
        speaking_settings.cache_clear()


def test_groq_error_falls_back_to_none(monkeypatch):
    _use_keys(monkeypatch, anthropic=None, groq="gsk_test")

    def boom(*a, **k):
        raise ollama_client.OllamaUnavailable("down")

    monkeypatch.setattr(ollama_client, "chat_json", boom)
    try:
        assert llm_client.grade_writing("x", "y") is None
    finally:
        speaking_settings.cache_clear()
        llm_client.reset_circuit()
