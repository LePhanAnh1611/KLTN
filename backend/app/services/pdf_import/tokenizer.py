"""Bước 2 của N1 — tách & chuẩn hóa từ bằng spaCy.

Ranh giới trách nhiệm ở đây có chủ đích: `load_nlp()` là chỗ DUY NHẤT biết đến
spaCy, còn `tokenize()` chỉ làm việc trên giao diện token (`.text`, `.lemma_`,
`.pos_`, `.is_alpha`, `.is_stop`). Nhờ vậy test dựng một `nlp` giả vài dòng là
chạy được, không phải tải model 12MB trong CI.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from app.services.pdf_import.errors import DependencyMissing
from app.services.pdf_import.extractor import INSTALL_HINT

DEFAULT_MODEL = "en_core_web_sm"

# Chỉ giữ 4 từ loại có giá trị học từ vựng. PROPN bị loại vì tên riêng
# (tên tác giả, tên chương) chiếm phần lớn rác trong một tài liệu thật.
ALLOWED_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Nhãn hiển thị. Bản thân UPOS được giữ nguyên trên TokenCandidate vì wordlist
# CEFR-J đã chuẩn hóa từ loại về đúng bộ UPOS — tra bằng nhãn tiếng Anh sẽ trượt.
POS_LABELS = {"NOUN": "noun", "VERB": "verb", "ADJ": "adjective", "ADV": "adverb"}

MIN_LEMMA_LENGTH = 3


@dataclass(frozen=True)
class TokenCandidate:
    """Một từ ứng viên sau khi chuẩn hóa — chưa có CEFR, chưa có chủ đề.

    `word` là **từ điển hình** (lemma) vì đó mới là thứ đáng học: tài liệu viết
    "absorbs"/"governments" nhưng người học cần "absorb"/"government". Dạng thật
    sự gặp trong tài liệu giữ ở `surface_form` để đối chiếu khi duyệt.
    """

    word: str
    lemma: str
    surface_form: str
    part_of_speech: str | None    # nhãn cho người đọc: "noun", "verb"...
    upos: str | None              # nhãn UPOS thô của spaCy — khóa tra CEFR
    occurrences: int
    example_sentence: str | None


def model_name() -> str:
    return os.getenv("PDF_IMPORT_SPACY_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_available() -> bool:
    """spaCy *và* model ngôn ngữ đều đã sẵn sàng chưa (dùng cho health check)."""
    try:
        import spacy
    except ImportError:
        return False
    return spacy.util.is_package(model_name())


@lru_cache(maxsize=1)
def load_nlp() -> Any:
    """Nạp pipeline spaCy (cache theo tiến trình — nạp model tốn vài giây).

    Tắt `ner`/`parser`: ta chỉ cần lemma + từ loại, bỏ hai thành phần này giúp
    xử lý một tài liệu 50 trang nhanh hơn đáng kể.
    """
    try:
        import spacy
    except ImportError as exc:
        raise DependencyMissing(f"Chưa cài spaCy - cài bằng: {INSTALL_HINT}") from exc

    name = model_name()
    try:
        return spacy.load(name, disable=["ner", "parser"])
    except OSError as exc:
        raise DependencyMissing(
            f"Chưa tải model spaCy '{name}' - cài bằng: python -m spacy download {name}"
        ) from exc


def reset_nlp_cache() -> None:
    """Buộc nạp lại model ở lần gọi sau (dùng trong test)."""
    load_nlp.cache_clear()


def _is_candidate(token: Any) -> bool:
    if not getattr(token, "is_alpha", False) or getattr(token, "is_stop", False):
        return False
    if getattr(token, "pos_", None) not in ALLOWED_POS:
        return False
    lemma = (getattr(token, "lemma_", "") or "").strip().lower()
    return len(lemma) >= MIN_LEMMA_LENGTH and lemma.isalpha()


def tokenize(sentences: Iterable[str], nlp: Any | None = None) -> list[TokenCandidate]:
    """Chuẩn hóa danh sách câu thành các từ ứng viên duy nhất theo *lemma*.

    Khử trùng lặp theo lemma (không theo mặt chữ): "studies"/"studied"/"study"
    là một từ để học, gộp lại thì số lần xuất hiện mới phản ánh đúng độ quan
    trọng của từ trong tài liệu.

    Câu ví dụ là câu **đầu tiên** chứa từ — bước 5 của N1. Chọn câu đầu thay vì
    câu dài nhất để giữ đúng mạch tài liệu người học đang đọc.
    """
    engine = nlp if nlp is not None else load_nlp()
    sentence_list = [s for s in sentences if s and s.strip()]
    if not sentence_list:
        return []

    surfaces: dict[str, str] = {}
    upos: dict[str, str] = {}
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}

    for sentence, doc in zip(sentence_list, engine.pipe(sentence_list)):
        for token in doc:
            if not _is_candidate(token):
                continue
            lemma = token.lemma_.strip().lower()
            counts[lemma] = counts.get(lemma, 0) + 1
            if lemma not in surfaces:
                surfaces[lemma] = (token.text or lemma).strip().lower()
                upos[lemma] = token.pos_
                examples[lemma] = sentence

    candidates = [
        TokenCandidate(
            word=lemma,
            lemma=lemma,
            surface_form=surfaces[lemma],
            part_of_speech=POS_LABELS.get(upos[lemma]),
            upos=upos[lemma],
            occurrences=counts[lemma],
            example_sentence=examples.get(lemma),
        )
        for lemma in counts
    ]
    # Từ xuất hiện nhiều nằm trên: đó là từ khóa của tài liệu, người học duyệt trước.
    candidates.sort(key=lambda c: (-c.occurrences, c.lemma))
    return candidates
