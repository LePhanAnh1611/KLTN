"""Endpoint /api/v1/speaking/* — kiểm hợp đồng API, không cần model thật."""
import io

import pytest

from app.core.security import create_access_token
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.speaking import pipeline as pipeline_module
from app.api.v1.endpoints import speaking as speaking_api
from app.speaking.asr.base import AsrUnavailable
from app.speaking.scoring import llm_scorer

from tests.speaking.conftest import FakeAsr


@pytest.fixture
def headers(db_session):
    user = register_user(
        db_session,
        RegisterRequest(email="sp.api@example.com", password="Abcd1234",
                        password_confirm="Abcd1234", display_name="U"),
    )
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def stub_engine(monkeypatch, fluent_transcript):
    """Thay Whisper + Ollama bằng đồ giả cho toàn bộ pipeline."""
    monkeypatch.setattr(pipeline_module, "_default_asr", lambda: FakeAsr(fluent_transcript))
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["a small bookshop near my university"], "level": 3, "reason": "ok",
    })
    from app.speaking.feedback import composer
    from app.speaking.scoring.ollama_client import OllamaUnavailable
    monkeypatch.setattr(composer, "chat_json",
                        lambda s, u, temperature=None: (_ for _ in ()).throw(
                            OllamaUnavailable("off")))


def _audio(name: str = "sample.wav", payload: bytes = b"RIFF....WAVEfmt "):
    return {"audio": (name, io.BytesIO(payload), "audio/wav")}


def test_assess_returns_full_schema(client, headers, stub_engine):
    response = client.post(
        "/api/v1/speaking/assess", headers=headers,
        files=_audio(),
        data={"task_prompt": "Describe a place you enjoy visiting and explain why."},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["transcript"].startswith("The place I enjoy most")
    assert set(body["scores"]) == {
        "fluency", "pronunciation", "grammar_vocab", "coherence_task",
    }
    for criterion in body["scores"].values():
        assert 1 <= criterion["level"] <= 4
        assert criterion["label"] and criterion["suggestion"]
        assert criterion["scored_by"] in {"rule", "llm", "fallback"}

    assert 1 <= body["overall_level"] <= 4
    assert body["developmental_feedback"].strip()
    assert body["rubric_version"] == "0.1"
    assert body["audio_metrics"]["pronunciation_source"] == "asr_confidence"
    # Rubric mục 8 — trạng thái chưa calibrate phải đến được giao diện
    assert any("calibrate" in w for w in body["warnings"])


def test_weights_accepted_as_json_form_field(client, headers, stub_engine):
    response = client.post(
        "/api/v1/speaking/assess", headers=headers, files=_audio(),
        data={"task_prompt": "task", "weights": '{"coherence_task": 3}'},
    )
    assert response.status_code == 200, response.text


def test_invalid_weights_rejected(client, headers, stub_engine):
    response = client.post(
        "/api/v1/speaking/assess", headers=headers, files=_audio(),
        data={"task_prompt": "task", "weights": "khong-phai-json"},
    )
    assert response.status_code == 422
    assert "Trọng số không hợp lệ" in response.json()["detail"]


def test_rejects_unsupported_format(client, headers, stub_engine):
    response = client.post(
        "/api/v1/speaking/assess", headers=headers,
        files={"audio": ("bai-noi.txt", io.BytesIO(b"abc"), "text/plain")},
        data={"task_prompt": "task"},
    )
    assert response.status_code == 400
    assert ".wav" in response.json()["detail"]


def test_rejects_empty_file(client, headers, stub_engine):
    response = client.post(
        "/api/v1/speaking/assess", headers=headers,
        files=_audio(payload=b""), data={"task_prompt": "task"},
    )
    assert response.status_code == 400


def test_rejects_oversized_file(client, headers, stub_engine, monkeypatch):
    from app.speaking.config import reset_settings_cache

    monkeypatch.setenv("SPEAKING_MAX_AUDIO_MB", "0.001")
    reset_settings_cache()
    try:
        response = client.post(
            "/api/v1/speaking/assess", headers=headers,
            files=_audio(payload=b"x" * 5000), data={"task_prompt": "task"},
        )
        assert response.status_code == 413
    finally:
        reset_settings_cache()


def test_task_prompt_is_required(client, headers, stub_engine):
    response = client.post("/api/v1/speaking/assess", headers=headers, files=_audio())
    assert response.status_code == 422


def test_asr_unavailable_returns_503_not_fake_scores(client, headers, monkeypatch):
    """Không có transcript thì KHÔNG được bịa điểm — báo lỗi hạ tầng."""
    class Broken:
        name = "broken"

        def transcribe(self, audio_path, language=None):
            raise AsrUnavailable("chưa cài faster-whisper")

    monkeypatch.setattr(pipeline_module, "_default_asr", lambda: Broken())

    response = client.post(
        "/api/v1/speaking/assess", headers=headers, files=_audio(),
        data={"task_prompt": "task"},
    )
    assert response.status_code == 503
    assert "chưa cài faster-whisper" in response.json()["detail"]


def test_temp_audio_file_is_deleted(client, headers, stub_engine, monkeypatch):
    """Privacy: giọng người học không được nằm lại trên đĩa sau khi chấm."""
    seen: dict[str, str] = {}
    original = pipeline_module.assess

    def spy(audio_path, *args, **kwargs):
        seen["path"] = audio_path
        return original(audio_path, *args, **kwargs)

    monkeypatch.setattr(speaking_api.pipeline, "assess", spy)

    client.post("/api/v1/speaking/assess", headers=headers, files=_audio(),
                data={"task_prompt": "task"})

    import os
    assert seen["path"]
    assert not os.path.exists(seen["path"])


@pytest.fixture
def groq_config(monkeypatch):
    """Ép cấu hình Groq cho health check.

    Health check đọc `GROQ_API_KEY`/`GROQ_MODEL`, mà những biến này có thật
    trong `.env` của máy dev -> không ép thì test đổi kết quả theo từng máy.
    """
    from app.speaking.config import reset_settings_cache

    def _set(api_key: str = "gsk_test", model: str = "test-model"):
        monkeypatch.setenv("GROQ_API_KEY", api_key)
        monkeypatch.setenv("GROQ_MODEL", model)
        reset_settings_cache()

    _set()
    yield _set
    reset_settings_cache()          # trả cache về cấu hình thật cho test sau


def test_health_reports_dependency_status(client, headers, monkeypatch, groq_config):
    monkeypatch.setattr(speaking_api.ollama_client, "installed_models", lambda: [])

    body = client.get("/api/v1/speaking/health", headers=headers).json()
    assert body["rubric_version"] == "0.1"
    assert body["rubric_calibrated"] is False
    assert body["llm_ready"] is False
    assert "Không kết nối được Groq" in body["llm_detail"]


def test_health_flags_missing_model(client, headers, monkeypatch, groq_config):
    """Key gọi được Groq nhưng model đang cấu hình không nằm trong danh sách."""
    monkeypatch.setattr(speaking_api.ollama_client, "installed_models",
                        lambda: ["openai/gpt-oss-20b"])
    body = client.get("/api/v1/speaking/health", headers=headers).json()

    assert body["llm_ready"] is False
    assert "GROQ_MODEL" in body["llm_detail"]
    assert "ollama pull" not in body["llm_detail"]


def test_health_flags_missing_api_key(client, headers, monkeypatch, groq_config):
    """Thiếu key là nguyên nhân hay gặp nhất — phải nói thẳng tên biến."""
    groq_config(api_key="")
    monkeypatch.setattr(speaking_api.ollama_client, "installed_models", lambda: [])

    body = client.get("/api/v1/speaking/health", headers=headers).json()
    assert body["llm_ready"] is False
    assert "GROQ_API_KEY" in body["llm_detail"]


def test_health_ready_when_configured_model_is_served(client, headers, monkeypatch,
                                                      groq_config):
    monkeypatch.setattr(speaking_api.ollama_client, "installed_models",
                        lambda: ["test-model", "openai/gpt-oss-20b"])
    body = client.get("/api/v1/speaking/health", headers=headers).json()

    assert body["llm_ready"] is True
    assert body["llm_detail"] == "Sẵn sàng"
    assert body["ollama_model"] == "test-model"      # tên trường cũ, giá trị model thật


def test_endpoints_require_auth(client):
    assert client.get("/api/v1/speaking/health").status_code == 401
    assert client.post("/api/v1/speaking/assess").status_code == 401
