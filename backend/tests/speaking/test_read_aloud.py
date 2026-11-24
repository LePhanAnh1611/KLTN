"""Đọc theo câu mẫu — chấm bằng cách đối chiếu với câu cho sẵn, KHÔNG dùng LLM."""
import io

import pytest

from app.core.security import create_access_token
from app.models.item import Item
from app.models.pronunciation_attempt import PronunciationAttempt
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.speaking import read_aloud
from app.speaking.features.accuracy import compare, normalize_words
from app.api.v1.endpoints import pronunciation as pron_api

from tests.speaking.conftest import FakeAsr, make_transcript

SENTENCE = "Baby is crying every day."


# ------------------------------------------------------------ Đối chiếu

def test_normalization_drops_punctuation_not_apostrophes():
    assert normalize_words("Baby is crying, every day!") == [
        "baby", "is", "crying", "every", "day",
    ]
    # ASR không nghe được dấu câu — tách "don't" thành 2 từ là phạt sai chỗ
    assert normalize_words("Don't stop.") == ["don't", "stop"]


def test_perfect_reading_scores_full_accuracy():
    result = compare(SENTENCE, ["Baby", "is", "crying", "every", "day"])
    assert result.accuracy == 1.0
    assert result.missed_words == []
    assert result.extra_words == []


def test_missing_word_is_reported():
    result = compare(SENTENCE, ["Baby", "is", "crying", "every"])
    assert result.accuracy == 0.8
    assert result.missed_words == ["day"]


def test_wrong_word_counts_as_missed_and_extra():
    result = compare(SENTENCE, ["Baby", "is", "trying", "every", "day"])
    assert result.missed_words == ["crying"]
    assert result.extra_words == ["trying"]


def test_extra_words_do_not_reduce_accuracy():
    """Đọc thêm mạo từ không phải là đọc sai câu."""
    result = compare(SENTENCE, ["The", "baby", "is", "crying", "every", "day"])
    assert result.accuracy == 1.0
    assert result.extra_words == ["The"]


def test_case_is_ignored():
    assert compare(SENTENCE, ["BABY", "IS", "CRYING", "EVERY", "DAY"]).accuracy == 1.0


def test_empty_reading():
    result = compare(SENTENCE, [])
    assert result.accuracy == 0.0
    assert len(result.missed_words) == 5


def test_confidence_is_attached_to_matched_words():
    result = compare(SENTENCE, ["Baby", "is", "crying", "every", "day"],
                     [0.9, 0.9, 0.4, 0.9, 0.9])
    crying = next(w for w in result.words if w.expected == "crying")
    assert crying.ok is True and crying.confidence == 0.4


# ------------------------------------------------------------ Chấm

def _transcript(words, confidence=0.95, wpm=140):
    spec, cursor, step = [], 0.0, 60.0 / wpm
    for word in words:
        spec.append((word, cursor, cursor + step, confidence))
        cursor += step
    return make_transcript(spec, duration=cursor)


def _assess(words, **kwargs):
    return read_aloud.assess_sentence(
        "f.wav", item_id=1, word="baby", expected_text=SENTENCE,
        asr=FakeAsr(_transcript(words, **kwargs)),
    )


def test_does_not_call_the_llm(monkeypatch):
    """Cả cái hay của chế độ này nằm ở chỗ không cần LLM (106s -> ~2s)."""
    from app.speaking.scoring import llm_scorer

    def boom(*args, **kwargs):
        raise AssertionError("đọc câu mẫu KHÔNG được gọi LLM")

    monkeypatch.setattr(llm_scorer, "chat_json", boom)
    result = _assess(["Baby", "is", "crying", "every", "day"])
    assert result.overall_level == 4


def test_perfect_reading_is_advanced():
    result = _assess(["Baby", "is", "crying", "every", "day"])
    assert result.accuracy == 1.0
    assert result.overall_level == 4
    assert [a.key for a in result.aspects] == ["accuracy", "clarity", "fluency"]


def test_overall_never_exceeds_reading_accuracy():
    """Đọc sai nửa câu mà vẫn Advanced vì giọng rõ là vô lý."""
    result = _assess(["Baby", "is"], confidence=0.99)

    accuracy_aspect = next(a for a in result.aspects if a.key == "accuracy")
    clarity_aspect = next(a for a in result.aspects if a.key == "clarity")
    assert clarity_aspect.level == 4          # giọng rất rõ
    assert result.overall_level <= accuracy_aspect.level


def test_missed_words_drive_the_suggestion():
    result = _assess(["Baby", "is", "every", "day"])
    assert "crying" in result.missed_words

    accuracy_aspect = next(a for a in result.aspects if a.key == "accuracy")
    assert "crying" in accuracy_aspect.suggestion


def test_correct_but_unclear_word_is_flagged():
    """Điều chế độ nói tự do không làm được: biết từ nào ĐÚNG mà đọc chưa rõ."""
    transcript = make_transcript([
        ("Baby", 0.0, 0.4, 0.95), ("is", 0.4, 0.6, 0.95),
        ("crying", 0.6, 1.1, 0.35), ("every", 1.1, 1.5, 0.95),
        ("day", 1.5, 1.9, 0.95),
    ], duration=1.9)
    result = read_aloud.assess_sentence(
        "f.wav", item_id=1, word="baby", expected_text=SENTENCE, asr=FakeAsr(transcript),
    )

    assert result.accuracy == 1.0                 # đọc đúng hết
    clarity = next(a for a in result.aspects if a.key == "clarity")
    assert "crying" in clarity.detail             # nhưng chỉ ra từ đọc chưa rõ


def test_hesitation_lowers_fluency():
    choppy = make_transcript([
        ("Baby", 0.0, 0.4, 0.95), ("is", 2.0, 2.3, 0.95),
        ("crying", 4.0, 4.5, 0.95), ("every", 6.0, 6.4, 0.95),
        ("day", 8.0, 8.4, 0.95),
    ], duration=8.4)
    result = read_aloud.assess_sentence(
        "f.wav", item_id=1, word="baby", expected_text=SENTENCE, asr=FakeAsr(choppy),
    )
    fluency = next(a for a in result.aspects if a.key == "fluency")
    assert fluency.level == 1
    assert "một hơi" in fluency.suggestion


def test_feedback_points_at_the_weakest_aspect():
    result = _assess(["Baby", "is"])
    assert "Việc nên làm tiếp theo" in result.feedback


def test_warns_when_nothing_was_heard():
    result = _assess([])
    assert any("micro" in w for w in result.warnings)


def test_always_warns_about_uncalibrated_scale():
    result = _assess(["Baby", "is", "crying", "every", "day"])
    assert any("chưa được đối chiếu" in w for w in result.warnings)


# ------------------------------------------------------------ API

@pytest.fixture
def setup(db_session):
    user = register_user(
        db_session,
        RegisterRequest(email="ra@example.com", password="Abcd1234",
                        password_confirm="Abcd1234", display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Set", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    with_example = Item(word_set_id=ws.id, word="baby", meaning="em bé", example=SENTENCE)
    without = Item(word_set_id=ws.id, word="lonely", meaning="cô đơn")
    db_session.add_all([with_example, without])
    db_session.commit()
    db_session.refresh(with_example)
    db_session.refresh(without)
    return user, headers, with_example, without


@pytest.fixture
def stub_asr(monkeypatch):
    from app.speaking import pipeline

    monkeypatch.setattr(
        pipeline, "_default_asr",
        lambda: FakeAsr(_transcript(["Baby", "is", "crying", "every", "day"])),
    )


def _post(client, headers, item_id, save=None):
    data = {"item_id": str(item_id)}
    if save is not None:
        data["save"] = str(save).lower()
    return client.post(
        "/api/v1/pronunciation/read-aloud", headers=headers,
        files={"audio": ("a.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
        data=data,
    )


def test_api_scores_and_saves(client, db_session, setup, stub_asr):
    _, headers, item, _ = setup

    response = _post(client, headers, item.id)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["word"] == "baby"
    assert body["expected_text"] == SENTENCE
    assert body["accuracy"] == 1.0
    assert body["attempt_id"] is not None
    assert len(body["words"]) == 5
    assert all(w["ok"] for w in body["words"])

    saved = db_session.get(PronunciationAttempt, body["attempt_id"])
    assert saved.kind == "sentence"
    assert saved.target_text == SENTENCE
    assert saved.score == 100.0
    assert saved.detail["missed_words"] == []


def test_api_rejects_item_without_example(client, setup, stub_asr):
    _, headers, _, without = setup

    response = _post(client, headers, without.id)
    assert response.status_code == 400
    assert "chưa có câu ví dụ" in response.json()["detail"]


def test_api_rejects_foreign_item(client, db_session, setup, stub_asr):
    _, _, item, _ = setup
    other = register_user(
        db_session,
        RegisterRequest(email="ra.other@example.com", password="Abcd1234",
                        password_confirm="Abcd1234", display_name="O"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}
    assert _post(client, headers, item.id).status_code == 404


def test_api_rejects_empty_audio(client, setup, stub_asr):
    _, headers, item, _ = setup
    response = client.post(
        "/api/v1/pronunciation/read-aloud", headers=headers,
        files={"audio": ("a.webm", io.BytesIO(b""), "audio/webm")},
        data={"item_id": str(item.id)},
    )
    assert response.status_code == 400


def test_history_survives_navigation(client, setup, stub_asr):
    """Kết quả nằm ở máy chủ, không phải state màn hình — đổi tab không mất."""
    _, headers, item, _ = setup
    _post(client, headers, item.id)
    _post(client, headers, item.id)

    rows = client.get(f"/api/v1/pronunciation/items/{item.id}/attempts",
                      headers=headers).json()
    assert len(rows) == 2
    assert rows[0]["kind"] == "sentence"
    assert rows[0]["target_text"] == SENTENCE
    assert rows[0]["detail"]["overall_level"] >= 1


def test_history_can_filter_by_kind(client, setup, stub_asr):
    _, headers, item, _ = setup
    _post(client, headers, item.id)
    client.post("/api/v1/pronunciation/attempts", headers=headers,
                json={"item_id": item.id, "score": 88})

    both = client.get(f"/api/v1/pronunciation/items/{item.id}/attempts",
                      headers=headers).json()
    assert {r["kind"] for r in both} == {"sentence", "word"}

    only_word = client.get(
        f"/api/v1/pronunciation/items/{item.id}/attempts?kind=word", headers=headers,
    ).json()
    assert [r["kind"] for r in only_word] == ["word"]


def test_save_false_does_not_persist(client, db_session, setup, stub_asr):
    _, headers, item, _ = setup
    body = _post(client, headers, item.id, save=False).json()
    assert body["attempt_id"] is None
    assert client.get(f"/api/v1/pronunciation/items/{item.id}/attempts",
                      headers=headers).json() == []


def test_asr_down_returns_503_not_fake_score(client, setup, monkeypatch):
    from app.speaking import pipeline
    from app.speaking.asr.base import AsrUnavailable

    class Broken:
        name = "broken"

        def transcribe(self, path, language=None):
            raise AsrUnavailable("chưa cài faster-whisper")

    monkeypatch.setattr(pipeline, "_default_asr", lambda: Broken())
    _, headers, item, _ = setup

    response = _post(client, headers, item.id)
    assert response.status_code == 503
    assert "faster-whisper" in response.json()["detail"]


def test_endpoints_require_auth(client):
    assert client.post("/api/v1/pronunciation/read-aloud").status_code == 401
    assert client.get("/api/v1/pronunciation/items/1/attempts").status_code == 401
