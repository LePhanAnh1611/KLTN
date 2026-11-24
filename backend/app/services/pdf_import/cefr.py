"""
Tra cứu trình độ CEFR của từ — bước 3 trong pipeline PDF → bộ từ (UC-87).

Nguyên tắc (theo docs/system-spec.md, nghiệp vụ N1):
  Trình độ CEFR gán bằng NGUỒN CHUẨN CÓ SẴN, KHÔNG để LLM đoán.
  LLM gán không nhất quán giữa các lần chạy nên không dùng làm dữ liệu nền
  cho mô hình được. Từ không có trong danh sách trả None — không bịa mức.

Nguồn được thiết kế dạng cắm được (Protocol), để sau thay bằng nguồn khác
(Oxford, EVP đã xin phép, hay bảng trong DB) mà không phải sửa service.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol, runtime_checkable

CefrLevel = str  # "A1" | "A2" | "B1" | "B2" | "C1" | "C2"

VALID_LEVELS = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})


@runtime_checkable
class CefrSource(Protocol):
    """Giao diện một nguồn gán trình độ CEFR."""

    name: str

    def lookup(self, lemma: str, upos: str | None = None) -> CefrLevel | None:
        """Trả mức CEFR của từ, hoặc None nếu không có trong nguồn."""
        ...


class CsvCefrSource:
    """
    Đọc wordlist từ CSV (cột: word, part_of_speech, cefr_level).

    File này sinh ra bởi app/scripts/build_cefr_wordlist.py từ:
      - CEFR-J Vocabulary Profile v1.5 (Tono Lab, TUFS) — A1–B2
      - Octanove Vocabulary Profile C1/C2 v1.0 (CC BY-SA 4.0) — C1–C2

    Nạp một lần vào bộ nhớ (~10k dòng, không đáng kể) rồi tra bằng dict.
    """

    name = "cefrj+octanove"

    def __init__(self, csv_path: Path) -> None:
        self._path = csv_path
        # khóa chính: (lemma, upos) — vì cùng chữ 'book' danh từ và động từ
        # có thể khác mức
        self._by_word_pos: dict[tuple[str, str], CefrLevel] = {}
        # khóa dự phòng: chỉ lemma, giữ mức thấp nhất trong các từ loại
        self._by_word: dict[str, CefrLevel] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(
                f"Không thấy wordlist CEFR tại {self._path}. "
                "Sinh file bằng: python -m app.scripts.build_cefr_wordlist "
                "--cefrj <file> --octanove <file> --out data/cefr_wordlist.csv"
            )

        order = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

        with self._path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                word = (row.get("word") or "").strip().lower()
                upos = (row.get("part_of_speech") or "X").strip().upper()
                level = (row.get("cefr_level") or "").strip().upper()

                if not word or level not in VALID_LEVELS:
                    continue

                self._by_word_pos[(word, upos)] = level

                current = self._by_word.get(word)
                if current is None or order[level] < order[current]:
                    self._by_word[word] = level

        if not self._by_word:
            raise ValueError(f"Wordlist {self._path} rỗng hoặc sai định dạng")

    def lookup(self, lemma: str, upos: str | None = None) -> CefrLevel | None:
        """
        Tra theo hai bước:
          1. Khớp chính xác (lemma, từ loại).
          2. Nếu trượt, khớp theo lemma bất kể từ loại.

        Bước 2 cần thiết vì nhãn từ loại của spaCy và của wordlist không phải
        lúc nào cũng trùng (spaCy gán AUX cho 'can', wordlist ghi VERB).
        Bỏ bước này sẽ tạo ra rất nhiều None sai.
        """
        key = lemma.strip().lower()
        if not key:
            return None

        if upos:
            hit = self._by_word_pos.get((key, upos.strip().upper()))
            if hit:
                return hit

        return self._by_word.get(key)

    def __len__(self) -> int:
        return len(self._by_word_pos)


# --------------------------------------------------------------------------
# Nạp một lần cho cả tiến trình
# --------------------------------------------------------------------------
_source: CefrSource | None = None


def get_cefr_source(csv_path: Path | None = None) -> CefrSource:
    """Trả nguồn CEFR dùng chung. Nạp lười, giữ lại cho các lần gọi sau."""
    global _source
    if _source is None:
        path = csv_path or Path(__file__).resolve().parents[3] / "data" / "cefr_wordlist.csv"
        _source = CsvCefrSource(path)
    return _source


def set_cefr_source(source: CefrSource) -> None:
    """Thay nguồn — dùng cho test, hoặc khi đổi sang nguồn khác."""
    global _source
    _source = source
