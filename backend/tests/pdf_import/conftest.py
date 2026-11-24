"""Đồ giả cho luồng tạo bộ từ từ PDF (UC-87).

Toàn bộ test chạy KHÔNG cần pdfplumber và KHÔNG cần spaCy — cùng cách làm với
`tests/speaking`. Tầng lõi chỉ phụ thuộc vào ba điểm cắm (`extractor`,
`tokenizer.load_nlp`, `cefr.CefrSource`) nên thay bằng đồ giả là đủ, và CI không
phải tải model ngôn ngữ.
"""
from __future__ import annotations

import pytest

from app.services.pdf_import import cefr, tokenizer
from app.services.pdf_import.extractor import ExtractedDocument

# Bộ dừng tối thiểu — đủ để kiểm rằng `tokenize` có loại stopword hay không.
STOP_WORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "is", "are", "be", "this",
    "that", "it", "for", "on", "with", "as", "by", "at", "from", "more",
}

# Vài đuôi thường gặp; lemmatizer thật thông minh hơn nhiều nhưng test chỉ cần
# chứng minh rằng các biến thể của cùng một từ được gộp về một dòng.
_SUFFIXES = (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", ""))


class FakeToken:
    def __init__(self, text: str, pos: str = "NOUN", lemma: str | None = None):
        self.text = text
        self.pos_ = pos
        self.lemma_ = lemma if lemma is not None else _lemmatize(text.lower())
        self.is_alpha = text.isalpha()
        self.is_stop = text.lower() in STOP_WORDS


def _lemmatize(word: str) -> str:
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)] + replacement
    return word


class FakeNlp:
    """spaCy giả: tách theo khoảng trắng, gán POS theo bảng tra sẵn.

    Mặc định mọi từ là NOUN; truyền `pos` để ép một từ thành VERB/PROPN… khi
    test cần (VD kiểm rằng PROPN bị loại).
    """

    def __init__(self, pos: dict[str, str] | None = None):
        self._pos = {k.lower(): v for k, v in (pos or {}).items()}
        self.seen: list[str] = []

    def _tokenize(self, sentence: str) -> list[FakeToken]:
        tokens = []
        for raw in sentence.replace(",", " ").replace(".", " ").split():
            word = raw.strip("\"'()[]").strip()
            if word:
                tokens.append(FakeToken(word, self._pos.get(word.lower(), "NOUN")))
        return tokens

    def pipe(self, sentences):
        for sentence in sentences:
            self.seen.append(sentence)
            yield self._tokenize(sentence)


class FakeCefrSource:
    """Nguồn CEFR giả — chứng minh điểm cắm hoạt động và mô phỏng 'từ lạ'.

    Hiện thực đúng giao diện `CefrSource`: `lookup(lemma, upos)`. Khóa có thể
    là "forest" (mọi từ loại) hoặc "book/VERB" (riêng một từ loại).
    """

    name = "fake"

    def __init__(self, levels: dict[str, str] | None = None):
        self._levels = {k.lower(): v for k, v in (levels or {}).items()}

    def __len__(self) -> int:
        return len(self._levels)

    def lookup(self, lemma: str, upos: str | None = None) -> str | None:
        key = lemma.strip().lower()
        if upos:
            hit = self._levels.get(f"{key}/{upos.strip().upper()}")
            if hit:
                return hit
        return self._levels.get(key)


def make_document(sentences: list[str], *, page_count: int = 1) -> ExtractedDocument:
    return ExtractedDocument(page_count=page_count, sentences=list(sentences))


@pytest.fixture
def fake_nlp(monkeypatch) -> FakeNlp:
    """Cắm spaCy giả vào `tokenizer.load_nlp` cho cả pipeline."""
    nlp = FakeNlp()
    monkeypatch.setattr(tokenizer, "load_nlp", lambda: nlp)
    return nlp


@pytest.fixture(autouse=True)
def _isolate_cefr_source():
    """Mỗi test bắt đầu với nguồn CEFR mặc định, không rò rỉ sang test khác."""
    yield
    cefr._source = None      # nạp lười lại từ file thật ở lần gọi sau


@pytest.fixture
def fake_cefr():
    """Trả về hàm cắm nguồn CEFR giả với bảng mức cho trước."""

    def _install(levels: dict[str, str] | None = None) -> FakeCefrSource:
        source = FakeCefrSource(levels)
        cefr.set_cefr_source(source)
        return source

    return _install


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Mặc định Ollama coi như KHÔNG chạy — test hermetic, không chạm mạng.

    Chặn ở `chat_json` (biên thật với Ollama) chứ không phải ở `topic.tag_topics`:
    nhờ vậy đường lùi BR-PDF-03 vẫn là code thật đang chạy, chứ không bị stub mất.
    Test nào cần chủ đề thì monkeypatch `chat_json` đè lại.
    """
    from app.speaking.scoring import ollama_client

    def _unavailable(*_args, **_kwargs):
        raise ollama_client.OllamaUnavailable("Ollama không chạy trong test")

    monkeypatch.setattr(ollama_client, "chat_json", _unavailable)
    monkeypatch.setattr(ollama_client, "is_available", lambda: False)
