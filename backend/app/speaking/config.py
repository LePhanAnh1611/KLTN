"""Cấu hình module luyện nói — đọc từ biến môi trường.

Tách khỏi `app.core.config` để module đứng riêng được: ai muốn bê module này
sang dự án khác chỉ cần mang thư mục `speaking/` mà không kéo theo cả Settings
của app. Đổi lại, các biến ở đây tự đọc `os.environ`.

Có một lối lùi về file `.env`: `app.core.config` dùng pydantic-settings, và
pydantic ĐỌC `.env` nhưng KHÔNG đổ ngược vào `os.environ`. Chạy tay bằng
`uvicorn` thì biến trong `.env` vô hình với `os.getenv`. Vì `GROQ_API_KEY` sống
ở `.env`, thiếu lối lùi này là module im lặng rơi về đường degrade.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Cùng thứ tự với `app.core.config`: chạy từ backend/ thì `.env` nằm ở thư mục cha.
_ENV_FILES = (Path(__file__).resolve().parents[3] / ".env", Path.cwd() / ".env")


@lru_cache(maxsize=1)
def _dotenv() -> dict[str, str]:
    """Đọc `.env` một lần. Lỗi đọc file KHÔNG được làm sập cấu hình."""
    values: dict[str, str] = {}
    for path in _ENV_FILES:
        try:
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, raw = line.partition("=")
                values.setdefault(key.strip(), raw.strip().strip("\"'"))
        except OSError:                                # noqa: PERF203
            continue
    return values


def _env(key: str, default: str) -> str:
    """Biến môi trường thật thắng; thiếu thì tra `.env`; thiếu nữa thì mặc định."""
    value = os.getenv(key)
    if value is None:
        value = _dotenv().get(key, default)
    return value.strip()


def _env_bool(key: str, default: bool) -> bool:
    return _env(key, "true" if default else "false").lower() in {"1", "true", "yes"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class SpeakingSettings:
    # ---- ASR (faster-whisper, chạy local) ----
    whisper_model: str = "base"          # tiny|base|small|medium|large-v3
    whisper_device: str = "cpu"          # cpu|cuda|auto
    whisper_compute_type: str = "int8"   # int8 cho CPU, float16 cho GPU
    whisper_download_root: str = ""
    beam_size: int = 5
    vad_filter: bool = True              # cắt khoảng lặng đầu/cuối trước khi nhận dạng

    # ---- LLM chấm C3/C4 (Groq Cloud, API OpenAI-compatible) ----
    # Trước đây là Ollama chạy local. Đổi sang Groq để không tốn CPU/RAM máy
    # chủ và trả lời nhanh hơn hẳn. Tên biến `ollama_*` giữ nguyên cho các chỗ
    # gọi cũ (timeout/temperature/URL health check) — xem `scoring/ollama_client`.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_sec: float = 90.0
    # Rubric mục 7.4 — nhiệt độ thấp để cùng bài nói ra cùng mức
    ollama_temperature: float = 0.1
    # Rubric mục 7.5 — chạy nhiều lần rồi lấy trung vị. 1 = tắt (mặc định, vì
    # mỗi lần chạy tốn vài giây CPU).
    llm_samples: int = 1

    default_language: str = "en"
    max_audio_mb: float = 25.0


@lru_cache(maxsize=1)
def speaking_settings() -> SpeakingSettings:
    return SpeakingSettings(
        whisper_model=_env("SPEAKING_WHISPER_MODEL", "base"),
        whisper_device=_env("SPEAKING_WHISPER_DEVICE", "cpu"),
        whisper_compute_type=_env("SPEAKING_WHISPER_COMPUTE_TYPE", "int8"),
        whisper_download_root=_env("SPEAKING_WHISPER_DOWNLOAD_ROOT", ""),
        beam_size=_env_int("SPEAKING_BEAM_SIZE", 5),
        vad_filter=_env_bool("SPEAKING_VAD_FILTER", True),
        groq_api_key=_env("GROQ_API_KEY", ""),
        groq_model=_env("GROQ_MODEL", "openai/gpt-oss-120b"),
        # Bỏ dấu "/" cuối để nối "/chat/completions" không thành "//".
        groq_base_url=_env("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        ollama_base_url=_env("SPEAKING_OLLAMA_URL", "http://localhost:11434"),
        ollama_model=_env("SPEAKING_OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_timeout_sec=_env_float("SPEAKING_OLLAMA_TIMEOUT", 90.0),
        ollama_temperature=_env_float("SPEAKING_OLLAMA_TEMPERATURE", 0.1),
        llm_samples=max(1, _env_int("SPEAKING_LLM_SAMPLES", 1)),
        default_language=_env("SPEAKING_LANGUAGE", "en"),
        max_audio_mb=_env_float("SPEAKING_MAX_AUDIO_MB", 25.0),
    )


def reset_settings_cache() -> None:
    speaking_settings.cache_clear()
    _dotenv.cache_clear()
