"""Chấm C3/C4 bằng LLM — kiểm 6 kỹ thuật giữ nhất quán ở rubric mục 7.

Ollama được monkeypatch: test phải chạy không cần model cục bộ.
"""
import pytest

from app.speaking.config import reset_settings_cache
from app.speaking.rubric import load_rubric
from app.speaking.scoring import llm_scorer
from app.speaking.scoring.ollama_client import OllamaUnavailable


@pytest.fixture
def rubric():
    return load_rubric()


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch):
    monkeypatch.delenv("SPEAKING_LLM_SAMPLES", raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def _capture(monkeypatch, payload):
    """Bắt prompt gửi đi để kiểm nội dung, và trả về payload dựng sẵn."""
    seen = {}

    def fake(system, user, temperature=None):
        seen["system"] = system
        seen["user"] = user
        seen["temperature"] = temperature
        return payload

    monkeypatch.setattr(llm_scorer, "chat_json", fake)
    return seen


# ------------------------------------------------- Mục 7.1 chấm từng tiêu chí

def test_scores_exactly_one_criterion_per_call(monkeypatch, rubric):
    seen = _capture(monkeypatch, {"evidence": ["I go school"], "level": 2, "reason": "Sai thì."})

    score = llm_scorer.score_criterion(rubric, "grammar_vocab", "I go school yesterday.")

    assert score.criterion == "grammar_vocab"
    assert score.level == 2
    assert score.scored_by == "llm"
    # prompt chỉ chứa mô tả của ĐÚNG tiêu chí đang chấm
    assert "C3" in seen["user"]
    assert "C4" not in seen["user"]


# ------------------------------------------------- Mục 7.2 evidence-first

def test_prompt_demands_evidence_before_level(monkeypatch, rubric):
    seen = _capture(monkeypatch, {"evidence": ["x"], "level": 3, "reason": "y"})
    llm_scorer.score_criterion(rubric, "grammar_vocab", "Some transcript here.")

    user = seen["user"]
    # thứ tự trong hướng dẫn VÀ trong schema JSON đều đặt evidence trước level
    assert user.index("Trích 1-3 đoạn") < user.index("chọn mức 1-4")
    assert user.index('"evidence"') < user.index('"level"')
    assert "NGUYÊN VĂN" in user


# ------------------------------------------------- Mục 7.3 few-shot anchors

def test_prompt_includes_anchor_examples_for_every_level(monkeypatch, rubric):
    seen = _capture(monkeypatch, {"evidence": ["x"], "level": 3, "reason": "y"})
    llm_scorer.score_criterion(rubric, "coherence_task", "abc", "Describe a place.")

    user = seen["user"]
    assert "VÍ DỤ MẪU ĐÃ CHẤM" in user
    for level in (1, 2, 3, 4):
        assert f"→ Mức {level}." in user


def test_coherence_prompt_carries_the_task(monkeypatch, rubric):
    """C4 không có đề bài thì không xét được 'bám đề'."""
    seen = _capture(monkeypatch, {"evidence": ["x"], "level": 3, "reason": "y"})
    llm_scorer.score_criterion(rubric, "coherence_task", "abc", "Describe your hometown.")

    assert "Describe your hometown." in seen["user"]
    assert "ĐỀ BÀI" in seen["user"]


def test_grammar_prompt_does_not_carry_the_task(monkeypatch, rubric):
    """C3 chấm ngữ pháp/từ vựng — đưa đề vào chỉ làm nhiễu."""
    seen = _capture(monkeypatch, {"evidence": ["x"], "level": 3, "reason": "y"})
    llm_scorer.score_criterion(rubric, "grammar_vocab", "abc", "Describe your hometown.")

    assert "ĐỀ BÀI" not in seen["user"]


# ------------------------------------------------- Mục 7.5 trung vị nhiều lần

def test_median_of_multiple_runs(monkeypatch, rubric):
    monkeypatch.setenv("SPEAKING_LLM_SAMPLES", "3")
    reset_settings_cache()

    levels = iter([4, 2, 2])
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["e"], "level": next(levels), "reason": "r",
    })

    score = llm_scorer.score_criterion(rubric, "grammar_vocab", "abc")
    assert score.level == 2
    assert "trung vị của 3 lần chấm" in score.reason


def test_median_rounds_down_when_split(monkeypatch, rubric):
    """Phân vân giữa hai mức thì báo mức thấp hơn — lời khuyên không được hụt."""
    monkeypatch.setenv("SPEAKING_LLM_SAMPLES", "2")
    reset_settings_cache()

    levels = iter([4, 3])
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["e"], "level": next(levels), "reason": "r",
    })

    assert llm_scorer.score_criterion(rubric, "grammar_vocab", "abc").level == 3


# ------------------------------------------------- Mục 7.6 mức + lý do

def test_returns_level_and_reason_and_rubric_suggestion(monkeypatch, rubric):
    _capture(monkeypatch, {
        "evidence": ["I go school yesterday"], "level": 1, "reason": "Sai thì cơ bản.",
    })
    score = llm_scorer.score_criterion(rubric, "grammar_vocab", "I go school yesterday")

    assert score.reason == "Sai thì cơ bản."
    assert score.evidence == ["I go school yesterday"]
    # gợi ý luôn lấy từ rubric, không để LLM tự nghĩ ra
    assert score.suggestion == rubric.criteria["grammar_vocab"].at(1).suggestion
    assert score.label == "Emerging"


# ------------------------------------------------- Xử lý đầu ra hỏng

@pytest.mark.parametrize("payload", [
    {"evidence": ["e"], "level": "ba", "reason": "r"},
    {"evidence": ["e"], "reason": "r"},
    {"evidence": ["e"], "level": None, "reason": "r"},
])
def test_invalid_level_falls_back_instead_of_guessing(monkeypatch, rubric, payload):
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: payload)
    score = llm_scorer.score_criterion(rubric, "grammar_vocab", "abc")

    assert score.scored_by == "fallback"
    assert "KHÔNG phản ánh bài nói" in score.reason


def test_level_out_of_range_is_clamped(monkeypatch, rubric):
    _capture(monkeypatch, {"evidence": ["e"], "level": 9, "reason": "r"})
    assert llm_scorer.score_criterion(rubric, "grammar_vocab", "abc").level == 4


def test_evidence_capped_at_three_items(monkeypatch, rubric):
    _capture(monkeypatch, {"evidence": [f"e{i}" for i in range(10)], "level": 3, "reason": "r"})
    assert len(llm_scorer.score_criterion(rubric, "grammar_vocab", "abc").evidence) == 3


def test_string_evidence_is_accepted(monkeypatch, rubric):
    """Model nhỏ hay trả chuỗi thay vì mảng — nhận cả hai, đừng vứt kết quả."""
    _capture(monkeypatch, {"evidence": "một đoạn duy nhất", "level": 3, "reason": "r"})
    assert llm_scorer.score_criterion(rubric, "grammar_vocab", "abc").evidence == [
        "một đoạn duy nhất",
    ]


def test_ollama_down_produces_honest_fallback(monkeypatch, rubric):
    def boom(system, user, temperature=None):
        raise OllamaUnavailable("connection refused")

    monkeypatch.setattr(llm_scorer, "chat_json", boom)
    score = llm_scorer.score_criterion(rubric, "coherence_task", "abc", "task")

    assert score.scored_by == "fallback"
    assert score.evidence == []            # không bịa bằng chứng
    assert "connection refused" in score.reason


# --------------------------- Lỗi phát hiện khi chạy thật với qwen2.5:7b

def test_evidence_that_copies_whole_answer_is_trimmed(monkeypatch, rubric):
    """Mô hình hay chép nguyên bài nói vào evidence — mất hết giá trị "chỉ chỗ"."""
    long_quote = " ".join(f"word{i}" for i in range(60))
    _capture(monkeypatch, {"evidence": [long_quote], "level": 3, "reason": "r"})

    evidence = llm_scorer.score_criterion(rubric, "grammar_vocab", long_quote).evidence[0]
    assert len(evidence.split()) <= llm_scorer.MAX_EVIDENCE_WORDS + 1
    assert evidence.endswith("…")


def test_short_evidence_is_left_alone(monkeypatch, rubric):
    _capture(monkeypatch, {"evidence": ["a small bookshop"], "level": 3, "reason": "r"})
    assert llm_scorer.score_criterion(
        rubric, "grammar_vocab", "abc",
    ).evidence == ["a small bookshop"]


def test_prompt_states_the_evidence_length_limit(monkeypatch, rubric):
    seen = _capture(monkeypatch, {"evidence": ["e"], "level": 3, "reason": "r"})
    llm_scorer.score_criterion(rubric, "grammar_vocab", "abc")

    assert f"tối đa {llm_scorer.MAX_EVIDENCE_WORDS} từ" in seen["user"]
    assert "KHÔNG chép lại toàn bộ bài" in seen["user"]


def test_language_requirement_is_in_the_system_prompt(monkeypatch, rubric):
    """Để ở cuối user prompt thì qwen2.5 bỏ qua — đã gặp thật."""
    seen = _capture(monkeypatch, {"evidence": ["e"], "level": 3, "reason": "r"})
    llm_scorer.score_criterion(rubric, "grammar_vocab", "abc")

    assert "TIẾNG VIỆT" in seen["system"]
    assert "chữ Hán" in seen["system"]


def test_chinese_reason_triggers_retry(monkeypatch, rubric):
    """Trôi sang chữ Hán -> thử lại; lần sau đúng thì dùng lời giải thích đó."""
    replies = iter([
        {"evidence": ["e1"], "level": 3, "reason": "地点和原因都涵盖了"},
        {"evidence": ["e2"], "level": 3, "reason": "Bám sát đề, có lý do rõ ràng."},
    ])
    monkeypatch.setattr(llm_scorer, "chat_json",
                        lambda s, u, temperature=None: next(replies))

    score = llm_scorer.score_criterion(rubric, "coherence_task", "abc", "task")
    assert score.level == 3
    assert score.reason == "Bám sát đề, có lý do rõ ràng."
    assert not llm_scorer._has_wrong_script(score.reason)


def test_persistent_chinese_reason_is_replaced_not_shown(monkeypatch, rubric):
    """Thử lại vẫn ra chữ Hán: giữ MỨC, nhưng không hiện đoạn người học không đọc được."""
    monkeypatch.setattr(llm_scorer, "chat_json", lambda s, u, temperature=None: {
        "evidence": ["e"], "level": 2, "reason": "安静所以我可以集中注意力",
    })

    score = llm_scorer.score_criterion(rubric, "grammar_vocab", "abc")
    assert score.level == 2                      # mức vẫn dùng được
    assert score.scored_by == "llm"
    assert not llm_scorer._has_wrong_script(score.reason)
    assert "ngôn ngữ khác" in score.reason


def test_wrong_script_detector():
    assert llm_scorer._has_wrong_script("lý do (安静)") is True
    assert llm_scorer._has_wrong_script("ひらがな") is True
    assert llm_scorer._has_wrong_script("Bám sát đề bài, đủ ý.") is False
