from app.scripts._console import use_utf8_console
"""
Chuẩn hóa CEFR-J Wordlist + Octanove C1/C2 thành một file wordlist duy nhất
cho pipeline gán trình độ CEFR (UC-87).

Nguồn dữ liệu:
  - CEFR-J Vocabulary Profile v1.5 — Tono Laboratory, Tokyo University of
    Foreign Studies. Dùng được cho nghiên cứu và thương mại, phải trích dẫn.
  - Octanove Vocabulary Profile C1/C2 v1.0 — CC BY-SA 4.0.
  Cả hai lấy qua: https://github.com/openlanguageprofiles/olp-en-cefrj

Đầu ra: backend/data/cefr_wordlist.csv  (cột: word, part_of_speech, cefr_level)

Cách chạy:
    python -m app.scripts.build_cefr_wordlist \
        --cefrj  data/raw/cefrj-vocabulary-profile-1.5.csv \
        --octanove data/raw/octanove-vocabulary-profile-c1c2-1.0.csv \
        --out    data/cefr_wordlist.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# 1. Gộp thang CEFR-J (chia nhỏ) về thang CEFR chuẩn A1–C2
# --------------------------------------------------------------------------
# CEFR-J chia nhỏ phần đầu vì đa số người học Nhật tập trung ở A1–A2.
# Hệ thống của ta dùng thang chuẩn nên phải gộp lại.
LEVEL_MAP = {
    "A1.1": "A1", "A1.2": "A1", "A1.3": "A1",
    "A2.1": "A2", "A2.2": "A2",
    "B1.1": "B1", "B1.2": "B1",
    "B2.1": "B2", "B2.2": "B2",
    "A1": "A1", "A2": "A2", "B1": "B1", "B2": "B2", "C1": "C1", "C2": "C2",
}

# Thứ tự để so sánh: từ xuất hiện ở nhiều mức thì giữ mức THẤP NHẤT,
# vì đó là lúc người học gặp nó lần đầu.
LEVEL_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

# --------------------------------------------------------------------------
# 2. Chuẩn hóa nhãn từ loại về bộ UPOS của spaCy
# --------------------------------------------------------------------------
# Bắt buộc, vì bước tra cứu lúc chạy dùng token.pos_ của spaCy làm khóa.
POS_MAP = {
    "noun": "NOUN", "n": "NOUN",
    "verb": "VERB", "v": "VERB",
    "adjective": "ADJ", "adj": "ADJ", "a": "ADJ",
    "adverb": "ADV", "adv": "ADV",
    "preposition": "ADP", "prep": "ADP",
    "conjunction": "CCONJ", "conj": "CCONJ",
    "pronoun": "PRON", "pron": "PRON",
    "determiner": "DET", "det": "DET",
    "article": "DET",
    "number": "NUM", "numeral": "NUM", "num": "NUM",
    "interjection": "INTJ", "int": "INTJ",
    "auxiliary": "AUX", "aux": "AUX",
    "modal": "AUX",
    "particle": "PART",
    "proper noun": "PROPN", "propn": "PROPN",
}

# Tên cột có thể gặp, xếp theo thứ tự ưu tiên khi dò
HEADWORD_HINTS = ["headword", "word", "lemma", "entry", "term"]
POS_HINTS = ["pos", "part_of_speech", "partofspeech", "word_class", "class"]
LEVEL_HINTS = ["cefr", "level", "cefr_level", "cefrj", "cefr-j"]


def detect_column(fieldnames: list[str], hints: list[str]) -> str | None:
    """Dò tên cột theo gợi ý. Khớp chính xác trước, khớp một phần sau."""
    normalized = {f.strip().lower().replace(" ", "_"): f for f in fieldnames}
    for hint in hints:
        if hint in normalized:
            return normalized[hint]
    for hint in hints:
        for norm, original in normalized.items():
            if hint in norm:
                return original
    return None


def normalize_pos(raw: str | None) -> str:
    """Đưa nhãn từ loại về UPOS. Không nhận ra thì trả 'X' (không xác định)."""
    if not raw:
        return "X"
    key = raw.strip().lower()
    if key in POS_MAP:
        return POS_MAP[key]
    # Nhiều bộ ghi kiểu "noun, verb" hoặc "adjective (attributive)"
    head = key.replace("(", " ").split()[0].strip(",;.")
    return POS_MAP.get(head, "X")


def normalize_level(raw: str | None) -> str | None:
    """Gộp mức CEFR-J về A1–C2. Không hợp lệ thì trả None (bỏ dòng)."""
    if not raw:
        return None
    key = raw.strip().upper().replace(" ", "")
    return LEVEL_MAP.get(key)


def read_source(path: Path, label: str) -> list[tuple[str, str, str]]:
    """Đọc một file CSV nguồn, trả về [(word, upos, level), ...]."""
    if not path.exists():
        sys.exit(f"LỖI: không thấy file {path}")

    rows: list[tuple[str, str, str]] = []
    skipped = Counter()

    # utf-8-sig để nuốt BOM nếu file xuất từ Excel
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            sys.exit(f"LỖI: {path} không có dòng tiêu đề")

        col_word = detect_column(reader.fieldnames, HEADWORD_HINTS)
        col_pos = detect_column(reader.fieldnames, POS_HINTS)
        col_level = detect_column(reader.fieldnames, LEVEL_HINTS)

        print(f"\n[{label}] {path.name}")
        print(f"  Cột có trong file : {reader.fieldnames}")
        print(f"  → dùng làm từ     : {col_word!r}")
        print(f"  → dùng làm từ loại: {col_pos!r}")
        print(f"  → dùng làm mức    : {col_level!r}")

        if not col_word or not col_level:
            sys.exit(
                f"LỖI: không dò được cột từ/mức trong {path.name}. "
                "Mở file xem tên cột thật rồi bổ sung vào *_HINTS ở đầu script."
            )

        for row in reader:
            word = (row.get(col_word) or "").strip().lower()
            level = normalize_level(row.get(col_level))
            upos = normalize_pos(row.get(col_pos) if col_pos else None)

            if not word:
                skipped["thiếu từ"] += 1
                continue
            if level is None:
                skipped["mức không hợp lệ"] += 1
                continue
            # Bỏ cụm nhiều từ: pipeline chỉ tra từ đơn sau khi lemmatize
            if " " in word or "-" in word:
                skipped["cụm nhiều từ"] += 1
                continue

            rows.append((word, upos, level))

    print(f"  Lấy được {len(rows):,} dòng hợp lệ")
    for reason, count in skipped.most_common():
        print(f"  Bỏ qua {count:,} dòng — {reason}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cefrj", required=True, type=Path,
                        help="CSV CEFR-J Vocabulary Profile (A1–B2)")
    parser.add_argument("--octanove", type=Path, default=None,
                        help="CSV Octanove Vocabulary Profile (C1–C2), tùy chọn")
    parser.add_argument("--out", required=True, type=Path,
                        help="File CSV đầu ra")
    args = parser.parse_args()

    all_rows = read_source(args.cefrj, "CEFR-J A1–B2")
    if args.octanove:
        all_rows += read_source(args.octanove, "Octanove C1–C2")

    # Khử trùng lặp theo (từ, từ loại). Cùng một từ ở nhiều mức thì giữ mức
    # THẤP NHẤT — đó là lúc người học gặp nó lần đầu.
    best: dict[tuple[str, str], str] = {}
    conflicts = 0
    for word, upos, level in all_rows:
        key = (word, upos)
        current = best.get(key)
        if current is None:
            best[key] = level
        elif LEVEL_ORDER[level] < LEVEL_ORDER[current]:
            best[key] = level
            conflicts += 1
        elif level != current:
            conflicts += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["word", "part_of_speech", "cefr_level"])
        for (word, upos), level in sorted(best.items()):
            writer.writerow([word, upos, level])

    # --- Báo cáo để đưa vào chương phương pháp của khóa luận ---
    by_level = Counter(level for level in best.values())
    by_pos = Counter(upos for _, upos in best)

    print(f"\n{'=' * 52}")
    print(f"Đã ghi {len(best):,} mục vào {args.out}")
    print(f"Số cặp (từ, từ loại) bị gán mức mâu thuẫn: {conflicts:,}")
    print("\nPhân bố theo mức CEFR:")
    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        count = by_level.get(level, 0)
        share = count / len(best) * 100 if best else 0
        print(f"  {level}: {count:>6,}  ({share:5.1f}%)")
    print("\nPhân bố theo từ loại (5 nhóm lớn nhất):")
    for upos, count in by_pos.most_common(5):
        print(f"  {upos:<6}: {count:>6,}")
    if by_pos.get("X"):
        print(f"\n  Cảnh báo: {by_pos['X']:,} mục không nhận ra từ loại (ghi 'X').")
        print("  Nếu con số này lớn, mở file nguồn xem nhãn từ loại thật")
        print("  rồi bổ sung vào POS_MAP ở đầu script.")


if __name__ == "__main__":
    use_utf8_console()
    main()
