"""Đối chiếu bài đọc với CÂU MẪU cho sẵn — lõi của chế độ đọc theo câu.

Khác hẳn nói tự do: ở đây ta BIẾT TRƯỚC người học phải nói gì. Điều đó đổi bản
chất việc chấm theo hai hướng:

- Đo được độ chính xác THẬT (từ nào đọc đúng, từ nào sai/thiếu), thay vì chỉ suy
  gián tiếp từ độ tin cậy của ASR như khi nói tự do.
- KHÔNG cần mô hình ngôn ngữ: ngữ pháp và bố cục ý đã nằm sẵn trong câu mẫu,
  người học không sáng tác gì cả. Bỏ LLM đưa thời gian chấm từ ~106s xuống ~2s.

Cách so: căn chỉnh hai dãy từ đã chuẩn hóa bằng `difflib`. Chuẩn hóa bỏ dấu câu
và hoa/thường vì ASR không nghe được dấu phẩy — phạt người học vì thiếu dấu chấm
là phạt sai chỗ.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

_PUNCT = re.compile(r"[^\w'\s]", re.UNICODE)


def normalize_words(text: str) -> list[str]:
    """Tách thành dãy từ đã bỏ dấu câu, hạ chữ thường.

    Giữ dấu nháy đơn để "don't" không vỡ thành "don" + "t".
    """
    cleaned = _PUNCT.sub(" ", unicodedata.normalize("NFC", text))
    return [w for w in cleaned.lower().split() if w]


@dataclass(frozen=True)
class WordCheck:
    """Một từ trong câu mẫu và kết quả đọc của người học."""

    expected: str
    # Từ ASR nghe được ở vị trí này; None = người học bỏ sót
    heard: str | None
    ok: bool
    # Độ tin cậy ASR của từ nghe được — thấp nghĩa là đọc không rõ dù đúng từ
    confidence: float | None = None


@dataclass(frozen=True)
class ReadAloudAccuracy:
    """Kết quả đối chiếu toàn câu."""

    expected_text: str
    words: list[WordCheck]
    correct_count: int
    expected_count: int
    # Từ người học nói thêm, không có trong câu mẫu
    extra_words: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """0..1 — tỉ lệ từ trong câu mẫu được đọc đúng."""
        return (self.correct_count / self.expected_count) if self.expected_count else 0.0

    @property
    def missed_words(self) -> list[str]:
        """Từ đọc sai hoặc bỏ sót — đây là thứ người học cần luyện lại."""
        return [w.expected for w in self.words if not w.ok]


def compare(
    expected_text: str,
    heard_words: list[str],
    confidences: list[float] | None = None,
) -> ReadAloudAccuracy:
    """Đối chiếu từ ASR nghe được với câu mẫu.

    `heard_words` là dãy từ THÔ từ ASR (chưa chuẩn hóa) để còn hiển thị lại cho
    người học đúng thứ họ đã nói.
    """
    expected = normalize_words(expected_text)
    heard_norm = [normalize_words(w)[0] if normalize_words(w) else "" for w in heard_words]
    confidences = confidences or [1.0] * len(heard_words)

    # Vị trí trong câu mẫu -> chỉ số từ ASR khớp với nó
    matched: dict[int, int] = {}
    matcher = SequenceMatcher(a=expected, b=heard_norm, autojunk=False)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            matched[block.a + offset] = block.b + offset

    words = [
        WordCheck(
            expected=word,
            heard=heard_words[matched[index]] if index in matched else None,
            ok=index in matched,
            confidence=(
                confidences[matched[index]]
                if index in matched and matched[index] < len(confidences) else None
            ),
        )
        for index, word in enumerate(expected)
    ]

    used = set(matched.values())
    extra = [heard_words[i] for i in range(len(heard_words)) if i not in used]

    return ReadAloudAccuracy(
        expected_text=expected_text.strip(),
        words=words,
        correct_count=sum(1 for w in words if w.ok),
        expected_count=len(expected),
        extra_words=extra,
    )
