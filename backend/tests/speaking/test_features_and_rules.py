"""Trích đặc trưng C1/C2 và quy về mức — hàm thuần, không cần model."""
from app.speaking.features import fluency, intelligibility
from app.speaking.rubric import load_rubric
from app.speaking.scoring import rule_scorer
from app.speaking.scoring.aggregate import normalize_weights, overall_level, summary_line
from app.speaking.types import CriterionScore

from tests.speaking.conftest import evenly_spaced, make_transcript


# ------------------------------------------------------------ C1 đặc trưng

def test_wpm_measured_on_speech_time_not_wall_clock():
    """Người dừng lâu đã bị phạt ở pause_ratio; không phạt lần hai qua WPM."""
    # 4 từ, mỗi từ 0.5s, xen 2s im lặng giữa từ 2 và 3
    transcript = make_transcript([
        ("one", 0.0, 0.5, 0.9), ("two", 0.5, 1.0, 0.9),
        ("three", 3.0, 3.5, 0.9), ("four", 3.5, 4.0, 0.9),
    ], duration=4.0)

    features = fluency.extract(transcript)

    assert features.speech_sec == 2.0            # 4.0s span - 2.0s lặng
    assert features.words_per_minute == 120.0    # 4 từ / 2s
    assert features.pause_count == 1
    assert features.longest_pause_sec == 2.0
    assert features.pause_ratio == 0.5


def test_leading_and_trailing_silence_ignored():
    """Người học bấm ghi âm rồi mới nói — im lặng đầu/cuối không phải mất trôi chảy."""
    transcript = make_transcript([
        ("hello", 5.0, 5.5, 0.9), ("there", 5.5, 6.0, 0.9),
    ], duration=12.0)

    features = fluency.extract(transcript)
    assert features.pause_count == 0
    assert features.pause_ratio == 0.0


def test_fillers_counted_but_real_words_are_not():
    transcript = make_transcript([
        ("Um,", 0.0, 0.3, 0.9), ("I", 0.3, 0.5, 0.9), ("like", 0.5, 0.8, 0.9),
        ("uh", 0.8, 1.1, 0.9), ("you", 1.1, 1.3, 0.9), ("know", 1.3, 1.6, 0.9),
    ], duration=1.6)

    features = fluency.extract(transcript)
    # "Um," và "uh" là từ đệm; "like"/"you know" là từ có nghĩa -> không đếm
    assert features.filler_count == 2


def test_empty_transcript_does_not_crash():
    features = fluency.extract(make_transcript([], duration=3.0))
    assert features.words_per_minute == 0.0
    assert features.filler_per_100_words == 0.0


# ------------------------------------------------------------ C1 chấm mức

def test_fluent_speech_scores_high(fluent_transcript):
    rubric = load_rubric()
    score = rule_scorer.score_fluency(fluency.extract(fluent_transcript), rubric)

    assert score.level == 4
    assert score.label == "Advanced"
    assert score.scored_by == "rule"
    assert score.suggestion == rubric.criteria["fluency"].at(4).suggestion


def test_halting_speech_scores_low(halting_transcript):
    score = rule_scorer.score_fluency(fluency.extract(halting_transcript), load_rubric())
    assert score.level == 1
    assert any("từ đệm" in e for e in score.evidence)


def test_level_follows_weakest_signal():
    """Nói nhanh nhưng nghỉ liên tục thì vẫn không trôi chảy."""
    fast_but_choppy = make_transcript([
        ("one", 0.0, 0.2, 0.9), ("two", 3.0, 3.2, 0.9),
        ("three", 6.0, 6.2, 0.9), ("four", 9.0, 9.2, 0.9),
    ], duration=9.2)

    score = rule_scorer.score_fluency(fluency.extract(fast_but_choppy), load_rubric())
    assert score.level == 1
    assert "ngắt nghỉ" in score.reason


def test_speaking_too_fast_is_penalised():
    slow = evenly_spaced("one two three four five six", wpm=130)
    frantic = evenly_spaced("one two three four five six", wpm=260)
    rubric = load_rubric()

    normal = rule_scorer.score_fluency(fluency.extract(slow), rubric)
    rushed = rule_scorer.score_fluency(fluency.extract(frantic), rubric)

    assert rushed.level < normal.level
    assert any("chậm lại" in e for e in rushed.evidence)


# ------------------------------------------------------------ C2

def test_intelligibility_flags_worst_words_first():
    transcript = make_transcript([
        ("clear", 0.0, 0.4, 0.98),
        ("muddy", 0.4, 0.8, 0.30),
        ("fuzzy", 0.8, 1.2, 0.10),
    ], duration=1.2)

    features = intelligibility.extract(transcript)
    assert features.low_confidence_words == ["fuzzy", "muddy"]   # tệ nhất lên trước
    assert 0.4 < features.avg_confidence < 0.5


def test_pronunciation_score_states_mvp_limitation(fluent_transcript):
    scorer = intelligibility.AsrConfidenceScorer()
    signal = scorer.score(fluent_transcript, "unused.wav")
    score = rule_scorer.score_pronunciation(signal, load_rubric(), fluent_transcript)

    assert score.level == 4
    # Rubric mục 4/C2 + mục 9: giới hạn phải nói thẳng trong bằng chứng
    assert any("chưa phải chấm chuẩn âm vị" in e for e in score.evidence)
    assert "asr_confidence" in score.reason


def test_pronunciation_scorer_is_pluggable(fluent_transcript):
    """Điểm cắm v2: đổi bộ chấm mà không sửa tầng scoring."""
    from tests.speaking.conftest import FakeGopScorer

    signal = FakeGopScorer(score=0.95).score(fluent_transcript, "unused.wav")
    score = rule_scorer.score_pronunciation(signal, load_rubric(), fluent_transcript)

    assert score.level == 4
    assert "gop" in score.reason
    # bộ chấm âm vị thật thì không kèm cảnh báo "chưa chấm âm vị"
    assert not any("chưa phải chấm chuẩn âm vị" in e for e in score.evidence)


# ------------------------------------------------------------ Tổng hợp

def _score(criterion: str, level: int, scored_by: str = "rule") -> CriterionScore:
    return CriterionScore(
        criterion=criterion, level=level, label="x", evidence=[],
        suggestion="y", scored_by=scored_by,
    )


def test_overall_is_weighted_average_rounded():
    scores = {
        "fluency": _score("fluency", 4),
        "pronunciation": _score("pronunciation", 4),
        "grammar_vocab": _score("grammar_vocab", 2),
        "coherence_task": _score("coherence_task", 2),
    }
    assert overall_level(scores) == 3               # trung bình 3.0

    # tăng trọng số C4 -> kéo mức chung xuống
    assert overall_level(scores, {"coherence_task": 5}) == 2


def test_unscored_criteria_excluded_from_overall():
    """'fallback' nghĩa là CHƯA CHẤM ĐƯỢC, không phải người học yếu."""
    scores = {
        "fluency": _score("fluency", 4),
        "pronunciation": _score("pronunciation", 4),
        "grammar_vocab": _score("grammar_vocab", 1, scored_by="fallback"),
        "coherence_task": _score("coherence_task", 1, scored_by="fallback"),
    }
    assert overall_level(scores) == 4


def test_overall_is_one_when_nothing_could_be_scored():
    scores = {"fluency": _score("fluency", 1, scored_by="fallback")}
    assert overall_level(scores) == 1


def test_weights_normalisation_ignores_junk():
    resolved = normalize_weights({"fluency": 3, "khong_ton_tai": 9, "pronunciation": -1})
    assert resolved["fluency"] == 3.0
    assert "khong_ton_tai" not in resolved
    assert resolved["pronunciation"] == 1.0          # âm -> bỏ, giữ mặc định

    assert normalize_weights({k: 0 for k in resolved}) == normalize_weights(None)


def test_summary_line_groups_criteria_by_level():
    scores = {
        "fluency": _score("fluency", 2),
        "pronunciation": _score("pronunciation", 3),
        "grammar_vocab": _score("grammar_vocab", 3),
        "coherence_task": _score("coherence_task", 3),
    }
    line = summary_line(scores, load_rubric().labels)
    assert "Developing về Độ trôi chảy" in line
    assert "Proficient về Độ dễ hiểu, Ngữ pháp & từ vựng, Mạch lạc & bám đề" in line


def test_half_is_rounded_down_consistently():
    """round() của Python làm tròn về số chẵn (2.5->2 nhưng 1.5->2) — không dùng.

    Ở đây phân vân giữa hai mức thì luôn báo mức thấp hơn, giống trung vị dưới
    trong llm_scorer.
    """
    from app.speaking.scoring.aggregate import _round_half_down

    assert [_round_half_down(v) for v in (1.5, 2.5, 3.5)] == [1, 2, 3]
    assert [_round_half_down(v) for v in (1.6, 2.4)] == [2, 2]

    half = {
        "fluency": _score("fluency", 4),
        "pronunciation": _score("pronunciation", 4),
        "grammar_vocab": _score("grammar_vocab", 1),
        "coherence_task": _score("coherence_task", 1),
    }
    assert overall_level(half) == 2          # trung bình đúng 2.5 -> xuống


def test_reason_does_not_claim_a_weakest_signal_when_all_are_equal(fluent_transcript):
    """Bài đạt mức 4 mà báo "chỉ số yếu nhất" thì người học tưởng đang bị trừ điểm."""
    score = rule_scorer.score_fluency(fluency.extract(fluent_transcript), load_rubric())

    assert score.level == 4
    assert "yếu nhất" not in score.reason
    assert "cùng một mức" in score.reason


def test_reason_names_the_limiting_signal_when_one_lags():
    choppy = make_transcript([
        ("one", 0.0, 0.2, 0.9), ("two", 3.0, 3.2, 0.9),
        ("three", 6.0, 6.2, 0.9), ("four", 9.0, 9.2, 0.9),
    ], duration=9.2)

    score = rule_scorer.score_fluency(fluency.extract(choppy), load_rubric())
    assert "giới hạn bởi" in score.reason
    assert "ngắt nghỉ" in score.reason
