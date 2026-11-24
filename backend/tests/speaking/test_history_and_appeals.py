"""Lưu lịch sử luyện nói + vòng phản hồi rubric (mục 9)."""
import io

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.speaking_attempt import SpeakingAttempt
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.api.v1.endpoints import speaking as speaking_api
from app.speaking import pipeline as pipeline_module
from app.speaking.scoring import llm_scorer

from tests.speaking.conftest import FakeAsr


def _register(db_session, email, role="learner"):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234",
                        password_confirm="Abcd1234", display_name=email.split("@")[0]),
    )
    if role != "learner":
        user.role = role
        db_session.commit()
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def headers(db_session):
    return _register(db_session, "spk.hist@example.com")[1]


@pytest.fixture
def stub_engine(monkeypatch, fluent_transcript):
    monkeypatch.setattr(pipeline_module, "_default_asr", lambda: FakeAsr(fluent_transcript))
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["a small bookshop"], "level": 3, "reason": "ok",
    })
    from app.speaking.feedback import composer
    from app.speaking.scoring.ollama_client import OllamaUnavailable
    monkeypatch.setattr(composer, "chat_json",
                        lambda s, u, temperature=None: (_ for _ in ()).throw(
                            OllamaUnavailable("off")))


def _assess(client, headers, prompt="Describe a place.", save=None):
    data = {"task_prompt": prompt}
    if save is not None:
        data["save"] = str(save).lower()
    return client.post(
        "/api/v1/speaking/assess", headers=headers,
        files={"audio": ("a.wav", io.BytesIO(b"RIFF....WAVEfmt "), "audio/wav")},
        data=data,
    )


# ---------------------------------------------------------------- Lưu trữ

def test_assessment_is_saved_and_returns_attempt_id(client, db_session, headers, stub_engine):
    body = _assess(client, headers).json()
    assert body["attempt_id"] is not None

    row = db_session.get(SpeakingAttempt, body["attempt_id"])
    assert row is not None
    assert row.transcript == body["transcript"]
    assert row.overall_level == body["overall_level"]
    assert row.rubric_version == "0.1"
    assert set(row.scores) == {
        "fluency", "pronunciation", "grammar_vocab", "coherence_task",
    }


def test_audio_is_not_persisted(client, db_session, headers, stub_engine):
    """Cam kết privacy: chỉ lưu transcript + kết quả, KHÔNG lưu giọng nói."""
    attempt_id = _assess(client, headers).json()["attempt_id"]
    row = db_session.get(SpeakingAttempt, attempt_id)

    columns = {c.name for c in row.__table__.columns}
    assert not any(name in columns for name in ("audio", "audio_path", "audio_blob"))


def test_save_false_skips_persistence(client, db_session, headers, stub_engine):
    body = _assess(client, headers, save=False).json()
    assert body["attempt_id"] is None
    assert db_session.execute(select(SpeakingAttempt)).scalars().all() == []


def test_history_lists_newest_first(client, headers, stub_engine):
    _assess(client, headers, prompt="Đề một")
    _assess(client, headers, prompt="Đề hai")

    body = client.get("/api/v1/speaking/attempts", headers=headers).json()
    assert body["total"] == 2
    assert [item["task_prompt"] for item in body["items"]] == ["Đề hai", "Đề một"]


def test_history_is_private(client, db_session, headers, stub_engine):
    _assess(client, headers)
    _, other = _register(db_session, "spk.other@example.com")

    assert client.get("/api/v1/speaking/attempts", headers=other).json()["total"] == 0


def test_cannot_open_someone_elses_attempt(client, db_session, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    _, other = _register(db_session, "spk.other2@example.com")

    assert client.get(f"/api/v1/speaking/attempts/{attempt_id}",
                      headers=other).status_code == 404


def test_progress_only_covers_latest_rubric_version(client, db_session, headers, stub_engine):
    """Rubric mục 8: sau khi calibrate, mức cũ và mới không so trực tiếp được."""
    _assess(client, headers)
    _assess(client, headers)

    # giả lập một lần chấm bằng rubric cũ
    oldest = db_session.execute(
        select(SpeakingAttempt).order_by(SpeakingAttempt.id)
    ).scalars().first()
    oldest.rubric_version = "0.0"
    db_session.commit()

    body = client.get("/api/v1/speaking/attempts", headers=headers).json()
    assert body["total"] == 2
    assert body["progress_rubric_version"] == "0.1"
    assert len(body["progress"]) == 1          # bản rubric cũ bị loại khỏi đường tiến bộ


def test_progress_points_are_oldest_first(client, headers, stub_engine):
    """Danh sách hiển thị mới nhất trước, nhưng đường tiến bộ phải cũ -> mới."""
    _assess(client, headers)
    _assess(client, headers)

    body = client.get("/api/v1/speaking/attempts", headers=headers).json()
    ids = [p["attempt_id"] for p in body["progress"]]
    assert ids == sorted(ids)


# ---------------------------------------------------- Phản hồi (rubric mục 9)

def test_appeal_records_gap_without_changing_score(client, db_session, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    before = db_session.get(SpeakingAttempt, attempt_id).scores["fluency"]["level"]

    response = client.post(
        f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=headers,
        json={"criterion": "fluency", "expected_level": 2, "comment": "Tôi nói khá đều mà."},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["expected_level"] == 2
    assert body["system_level"] == before
    assert body["status"] == "open"

    # KHÔNG tự sửa điểm — nếu sửa thì rubric mất hết ý nghĩa
    db_session.expire_all()
    assert db_session.get(SpeakingAttempt, attempt_id).scores["fluency"]["level"] == before


def test_appeal_marks_attempt_in_history(client, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=headers,
                json={"criterion": "overall", "comment": "chưa đúng"})

    body = client.get("/api/v1/speaking/attempts", headers=headers).json()
    assert body["items"][0]["has_appeal"] is True


def test_duplicate_appeal_for_same_criterion_conflicts(client, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    payload = {"criterion": "fluency", "comment": "lần một"}

    assert client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals",
                       headers=headers, json=payload).status_code == 201
    assert client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals",
                       headers=headers, json=payload).status_code == 409

    # tiêu chí khác thì vẫn gửi được
    assert client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=headers,
                       json={"criterion": "grammar_vocab", "comment": "x"}).status_code == 201


def test_cannot_appeal_someone_elses_attempt(client, db_session, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    _, other = _register(db_session, "spk.other3@example.com")

    assert client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=other,
                       json={"criterion": "fluency", "comment": "x"}).status_code == 404


def test_appeal_rejects_unknown_criterion(client, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    assert client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=headers,
                       json={"criterion": "khong_co", "comment": "x"}).status_code == 422


# ---------------------------------------------------------------- Quản trị

def test_admin_queue_sorts_signal_by_gap(client, db_session, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    client.post(f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=headers,
                json={"criterion": "fluency", "expected_level": 1,
                      "comment": "chấm cao quá"})

    _, admin = _register(db_session, "spk.admin@example.com", role="admin")
    rows = client.get("/api/v1/admin/speaking-appeals", headers=admin).json()

    assert len(rows) == 1
    row = rows[0]
    assert row["criterion"] == "fluency"
    assert row["expected_level"] == 1
    assert row["system_level"] is not None
    assert row["gap"] == abs(row["system_level"] - 1)
    # kèm transcript để người làm rubric xét lại descriptor mà không phải tra thêm
    assert row["transcript"]
    assert row["rubric_version"] == "0.1"


def test_admin_can_mark_reviewed(client, db_session, headers, stub_engine):
    attempt_id = _assess(client, headers).json()["attempt_id"]
    appeal_id = client.post(
        f"/api/v1/speaking/attempts/{attempt_id}/appeals", headers=headers,
        json={"criterion": "overall", "comment": "x"},
    ).json()["id"]

    _, admin = _register(db_session, "spk.admin2@example.com", role="admin")
    assert client.post(f"/api/v1/admin/speaking-appeals/{appeal_id}/reviewed",
                       headers=admin).status_code == 204

    assert client.get("/api/v1/admin/speaking-appeals", headers=admin).json() == []
    assert len(client.get("/api/v1/admin/speaking-appeals?only_open=false",
                          headers=admin).json()) == 1


def test_learner_cannot_read_appeal_queue(client, headers):
    assert client.get("/api/v1/admin/speaking-appeals", headers=headers).status_code == 403


def test_new_endpoints_require_auth(client):
    assert client.get("/api/v1/speaking/attempts").status_code == 401
    assert client.post("/api/v1/speaking/attempts/1/appeals", json={}).status_code == 401
