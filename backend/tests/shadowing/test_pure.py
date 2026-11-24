"""UC-97 — các mảnh thuần: nhận dạng link, đọc file phụ đề, cắt câu, hồ sơ CEFR.

Câu mẫu trong test do nhóm tự viết, không lấy từ phụ đề video thật.
"""
import pytest

from app.services.shadowing import CaptionError, Snippet
from app.services.shadowing import profile, segmenter
from app.services.shadowing.subtitles import parse_subtitles
from app.services.shadowing.youtube import parse_video_id

VID = "abcDEF12_-x"


# ------------------------------------------------------------ Link YouTube

@pytest.mark.parametrize("url", [
    VID,
    f"https://www.youtube.com/watch?v={VID}",
    f"https://www.youtube.com/watch?v={VID}&t=42s&list=PL123",
    f"https://youtu.be/{VID}?si=xyz",
    f"https://m.youtube.com/watch?v={VID}",
    f"https://www.youtube.com/embed/{VID}",
    f"https://www.youtube.com/shorts/{VID}",
    f"youtube.com/watch?v={VID}",
])
def test_parse_video_id_accepts_common_forms(url):
    assert parse_video_id(url) == VID


@pytest.mark.parametrize("url", [
    "", "https://vimeo.com/123456", "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/channel/UCabc", "not a link",
])
def test_parse_video_id_rejects_invalid(url):
    with pytest.raises(ValueError):
        parse_video_id(url)


# ------------------------------------------------------------ File phụ đề

SRT = """1
00:00:01,000 --> 00:00:03,500
<i>Good morning,</i> everyone.

2
00:00:03,600 --> 00:00:06,000
Today we talk about our plans.
"""

VTT = """WEBVTT

NOTE made by hand

00:01.000 --> 00:03.500
Good morning, everyone.

00:03.600 --> 00:06.000 align:start
Today we talk about our plans.
"""


@pytest.mark.parametrize("content", [SRT, VTT])
def test_parse_srt_and_vtt(content):
    snippets = parse_subtitles(content)
    assert [s.text for s in snippets] == ["Good morning, everyone.", "Today we talk about our plans."]
    assert snippets[0].start == 1.0
    assert snippets[1].duration == pytest.approx(2.4)


def test_parse_empty_subtitles_raises():
    with pytest.raises(CaptionError):
        parse_subtitles("just some text without timing")


# ------------------------------------------------------------ Cắt câu

def _snips(rows):
    return [Snippet(text=t, start=s, duration=d) for t, s, d in rows]


def test_punctuated_captions_merge_into_sentences():
    segs = segmenter.segment(_snips([
        ("I usually wake up early", 0.0, 1.8),
        ("and make a cup of tea.", 1.8, 1.7),
        ("Then I check my email", 3.6, 1.6),
        ("before work.", 5.2, 1.0),
    ]))
    assert [s.text for s in segs] == [
        "I usually wake up early and make a cup of tea.",
        "Then I check my email before work.",
    ]
    assert segs[0].start == 0.0 and segs[1].index == 1


def test_auto_captions_without_punctuation_break_near_target_length():
    rows = [(f"word{i} goes here now", i * 2.0, 2.0) for i in range(10)]  # 20 giây, không dấu câu
    segs = segmenter.segment(_snips(rows))
    assert len(segs) >= 3
    assert all(s.duration <= segmenter.MAX_SEC for s in segs)


def test_long_silence_starts_new_segment():
    segs = segmenter.segment(_snips([
        ("first part of the talk", 0.0, 2.0),
        ("second part after a pause", 5.0, 2.0),
    ]))
    assert len(segs) == 2


def test_segment_never_exceeds_max_length():
    rows = [(f"this is chunk {i} of text", i * 3.0, 3.0) for i in range(8)]
    segs = segmenter.segment(_snips(rows))
    assert all(s.duration <= segmenter.MAX_SEC + 1e-6 for s in segs)


def test_annotations_removed_and_overlap_fixed():
    segs = segmenter.segment(_snips([
        ("[Music]", 0.0, 2.0),
        (">> Welcome to the show today", 2.0, 5.0),   # kéo dài chồng lên mảnh sau
        ("we have a great guest.", 4.0, 2.0),
    ]))
    assert len(segs) == 1
    assert segs[0].text == "Welcome to the show today we have a great guest."
    assert segs[0].start == 2.0 and segs[0].end == 6.0


def test_short_fragment_absorbed_into_previous():
    segs = segmenter.segment(_snips([
        ("We finished the project last week.", 0.0, 3.0),
        ("Thanks.", 3.1, 0.8),
    ]))
    assert len(segs) == 1
    assert segs[0].text.endswith("Thanks.")


def test_normalize_edited_rejects_bad_timing():
    with pytest.raises(ValueError):
        segmenter.normalize_edited([{"start": 3, "end": 2, "text": "bad"}])
    segs = segmenter.normalize_edited([
        {"start": 5, "end": 7, "text": "second"},
        {"start": 1, "end": 3, "text": "first"},
        {"start": 8, "end": 9, "text": "  "},
    ])
    assert [(s.index, s.text) for s in segs] == [(0, "first"), (1, "second")]


# ------------------------------------------------------------ Hồ sơ CEFR

class FakeCefr:
    name = "fake"

    def __init__(self, table):
        self.table = table

    def lookup(self, lemma, upos=None):
        return self.table.get(lemma)


def test_vocab_profile_level_uses_95_percent_coverage():
    table = {w: "A1" for w in ["i", "like", "the", "cat", "dog", "a", "is", "my"]}
    table["ubiquitous"] = "C1"
    # 20 từ A1 + 1 từ C1: 20/21 = 95,2% ≥ 95% → video mức A1
    text = " ".join(["I like the cat"] * 4) + " my dog is a ubiquitous"
    result = profile.vocab_profile([text], FakeCefr(table))
    assert result["known_words"] == 21
    assert result["by_level"]["C1"] == 1
    assert result["level"] == "A1"

    harder = "I like the ubiquitous ubiquitous cat"
    assert profile.vocab_profile([harder], FakeCefr(table))["level"] == "C1"


def test_unknown_words_are_not_guessed():
    result = profile.vocab_profile(["Zorblax visited Hanoi"], FakeCefr({"visit": "A2"}))
    assert result["known_words"] == 1          # "visited" → "visit"
    assert result["total_words"] == 3
    assert result["level"] == "A2"


def test_words_per_minute():
    segs = [{"start": 0, "end": 3, "text": "one two three four five"},
            {"start": 3, "end": 6, "text": "six seven eight nine ten"}]
    assert profile.words_per_minute(segs) == 100.0
