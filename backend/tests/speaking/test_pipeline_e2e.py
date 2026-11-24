"""End-to-end: audio (giả) → JSON đầy đủ theo schema.

Dùng ASR giả + Ollama giả nên chạy được ở CI không có model.
"""
import pytest

from app.speaking import pipeline
from app.speaking.rubric import CRITERIA, load_rubric
from app.speaking.scoring import llm_scorer

from tests.speaking.conftest import FakeAsr, FakeGopScorer


@pytest.fixture
def stub_llm(monkeypatch):
    """Ollama trả mức 3 cho mọi tiêu chí."""
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["the owner always recommends something unexpected"],
        "level": 3,
        "reason": "Cấu trúc đa dạng, lỗi lẻ tẻ.",
    })
    # nhận xét tổng hợp cũng đi qua Ollama -> chặn luôn để dùng bản ghép rubric
    from app.speaking.feedback import composer
    from app.speaking.scoring.ollama_client import OllamaUnavailable

    def no_llm(system, user, temperature=None):
        raise OllamaUnavailable("tắt trong test")

    monkeypatch.setattr(composer, "chat_json", no_llm)


def test_full_assessment_matches_output_schema(fluent_transcript, stub_llm):
    result = pipeline.assess(
        "fake.wav",
        "Describe a place you enjoy visiting and explain why.",
        asr=FakeAsr(fluent_transcript),
    )

    assert result.transcript.startswith("The place I enjoy most")

    metrics = result.audio_metrics
    for key in ("duration_sec", "words_per_minute", "pause_ratio",
                "filler_count", "asr_avg_confidence"):
        assert key in metrics, key
    assert metrics["pronunciation_source"] == "asr_confidence"

    # đủ 4 tiêu chí, mỗi tiêu chí có mức + evidence + suggestion
    assert set(result.scores) == set(CRITERIA)
    for key, score in result.scores.items():
        assert 1 <= score.level <= 4
        assert score.label
        assert score.suggestion
        assert score.scored_by in {"rule", "llm", "fallback"}

    assert 1 <= result.overall_level <= 4
    assert result.developmental_feedback.strip()


def test_suggestions_come_from_the_rubric(fluent_transcript, stub_llm):
    """Gợi ý phải TRÍCH từ rubric, không do LLM tự nghĩ."""
    rubric = load_rubric()
    result = pipeline.assess("fake.wav", "task", asr=FakeAsr(fluent_transcript))

    for key, score in result.scores.items():
        assert score.suggestion == rubric.criteria[key].at(score.level).suggestion


def test_language_is_passed_through_to_asr(fluent_transcript, stub_llm):
    asr = FakeAsr(fluent_transcript)
    pipeline.assess("fake.wav", "task", language="vi", asr=asr)
    assert asr.calls == [("fake.wav", "vi")]


def test_weights_change_overall_level(fluent_transcript, monkeypatch):
    """C1/C2 mức 4, C3/C4 mức 1 -> dồn trọng số sang C3/C4 phải kéo tổng xuống."""
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["e"], "level": 1, "reason": "r",
    })
    from app.speaking.feedback import composer
    from app.speaking.scoring.ollama_client import OllamaUnavailable
    monkeypatch.setattr(composer, "chat_json",
                        lambda s, u, temperature=None: (_ for _ in ()).throw(
                            OllamaUnavailable("off")))

    balanced = pipeline.assess("f.wav", "t", asr=FakeAsr(fluent_transcript))
    skewed = pipeline.assess(
        "f.wav", "t", asr=FakeAsr(fluent_transcript),
        weights={"grammar_vocab": 5, "coherence_task": 5},
    )
    assert skewed.overall_level < balanced.overall_level


def test_v2_pronunciation_scorer_plugs_in(fluent_transcript, stub_llm):
    """Tiêu chí nghiệm thu: điểm cắm module chấm phát âm v2."""
    result = pipeline.assess(
        "fake.wav", "task",
        asr=FakeAsr(fluent_transcript),
        pronunciation_scorer=FakeGopScorer(score=0.95),
    )
    assert result.audio_metrics["pronunciation_source"] == "gop"
    assert "gop" in result.scores["pronunciation"].reason


def test_weak_speech_gets_low_levels_and_actionable_feedback(halting_transcript, monkeypatch):
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["I like the beach"], "level": 1, "reason": "Ý rời rạc.",
    })
    from app.speaking.feedback import composer
    from app.speaking.scoring.ollama_client import OllamaUnavailable
    monkeypatch.setattr(composer, "chat_json",
                        lambda s, u, temperature=None: (_ for _ in ()).throw(
                            OllamaUnavailable("off")))

    result = pipeline.assess("f.wav", "Describe a place.", asr=FakeAsr(halting_transcript))

    assert result.scores["fluency"].level == 1
    assert result.overall_level == 1
    # nhận xét phải chỉ ra MỘT việc nên làm tiếp theo
    assert "Việc nên làm tiếp theo" in result.developmental_feedback


def test_warns_when_recording_too_short(stub_llm):
    from tests.speaking.conftest import make_transcript

    tiny = make_transcript([("hi", 0.0, 0.3, 0.9)], duration=1.0)
    result = pipeline.assess("f.wav", "task", asr=FakeAsr(tiny))

    assert any("quá ngắn" in w for w in result.warnings)
    assert any("không có ý nghĩa" in w for w in result.warnings)


def test_warns_when_audio_is_mostly_silence(stub_llm):
    from tests.speaking.conftest import make_transcript

    noisy = make_transcript(
        [("hmm", 0.0, 0.5, 0.2)] * 8, duration=20.0, no_speech_prob=0.9,
    )
    result = pipeline.assess("f.wav", "task", asr=FakeAsr(noisy))

    assert any("không phải giọng nói" in w for w in result.warnings)
    assert any("Độ tin cậy nhận dạng rất thấp" in w for w in result.warnings)


def test_always_warns_while_rubric_uncalibrated(fluent_transcript, stub_llm):
    """Rubric mục 8 — chưa đối chiếu người chấm thật thì phải nói ra."""
    result = pipeline.assess("f.wav", "task", asr=FakeAsr(fluent_transcript))
    assert any("chưa được calibrate" in w for w in result.warnings)


def test_llm_down_still_returns_c1_c2(fluent_transcript, monkeypatch):
    """Ollama chết vẫn phải trả về hai tiêu chí đo được, kèm cảnh báo trung thực."""
    from app.speaking.feedback import composer
    from app.speaking.scoring.ollama_client import OllamaUnavailable

    def boom(system, user, temperature=None):
        raise OllamaUnavailable("connection refused")

    monkeypatch.setattr(llm_scorer, "chat_json", boom)
    monkeypatch.setattr(composer, "chat_json", boom)

    result = pipeline.assess("f.wav", "task", asr=FakeAsr(fluent_transcript))

    assert result.scores["fluency"].scored_by == "rule"
    assert result.scores["grammar_vocab"].scored_by == "fallback"
    # mức chung chỉ tính trên tiêu chí chấm được -> không bị kéo xuống oan
    assert result.overall_level == 4
    assert any("mô hình ngôn ngữ cục bộ không sẵn sàng" in w for w in result.warnings)
    assert "Chưa chấm được" in result.developmental_feedback


def test_use_llm_false_skips_ollama_entirely(fluent_transcript, monkeypatch):
    def boom(system, user, temperature=None):
        raise AssertionError("không được gọi Ollama khi use_llm=False")

    monkeypatch.setattr(llm_scorer, "chat_json", boom)
    result = pipeline.assess(
        "f.wav", "task", asr=FakeAsr(fluent_transcript), use_llm=False,
    )
    assert result.scores["coherence_task"].scored_by == "fallback"
