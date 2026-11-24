"""Hồ sơ từ vựng CEFR + tốc độ nói của một video — cấp độ do dữ liệu quyết định.

Cấp độ video = mức THẤP NHẤT mà ≥ COVERAGE (95%) số từ tra được nằm ở mức đó trở
xuống. Ngưỡng 95% lấy từ nghiên cứu độ phủ từ vựng cần để hiểu văn bản
(Laufer 1989; Hu & Nation 2000).

Nguồn CEFR dùng chung với UC-87 (`pdf_import.cefr`: CEFR-J + Octanove) — KHÔNG
để LLM đoán mức. Từ không có trong danh sách (tên riêng, từ hiếm) không bị gán
mức bừa: chỉ đếm riêng và báo tỉ lệ tra được.
"""
from __future__ import annotations

from collections import Counter

from app.services.pdf_import.cefr import CefrSource, get_cefr_source
from app.speaking.features.accuracy import normalize_words

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
COVERAGE = 0.95


def _candidates(word: str) -> list[str]:
    """Dạng gốc gần đúng, không cần spaCy: đủ cho việc ước lượng cấp độ."""
    w = word.strip("'")
    if w.endswith("'s"):
        w = w[:-2]
    forms = [w]
    if w.endswith("ies") and len(w) > 4:
        forms.append(w[:-3] + "y")
    if w.endswith("es") and len(w) > 3:
        forms.append(w[:-2])
    if w.endswith("s") and len(w) > 3:
        forms.append(w[:-1])
    if w.endswith("ied") and len(w) > 4:
        forms.append(w[:-3] + "y")
    if w.endswith("ed") and len(w) > 3:
        forms += [w[:-2], w[:-1]]
    if w.endswith("ing") and len(w) > 4:
        forms += [w[:-3], w[:-3] + "e"]
    return forms


def _lookup(source: CefrSource, word: str) -> str | None:
    for form in _candidates(word):
        level = source.lookup(form)
        if level:
            return level
    return None


def vocab_profile(texts: list[str], source: CefrSource | None = None) -> dict:
    """Đếm từ theo mức CEFR và suy ra cấp độ của cả đoạn."""
    source = source or get_cefr_source()
    counts: Counter[str] = Counter()
    unknown = 0
    total = 0
    for text in texts:
        for word in normalize_words(text):
            if any(ch.isdigit() for ch in word):
                continue
            total += 1
            level = _lookup(source, word)
            if level:
                counts[level] += 1
            else:
                unknown += 1

    known = total - unknown
    level: str | None = None
    if known:
        cumulative = 0
        for lv in LEVELS:
            cumulative += counts[lv]
            if cumulative / known >= COVERAGE:
                level = lv
                break

    return {
        "level": level,
        "total_words": total,
        "known_words": known,
        "known_ratio": round(known / total, 4) if total else 0.0,
        "by_level": {lv: counts[lv] for lv in LEVELS},
        "coverage_threshold": COVERAGE,
        "source": getattr(source, "name", "cefr"),
    }


def words_per_minute(segments: list[dict]) -> float | None:
    """Tốc độ nói trung bình trên phần có lời (tổng thời lượng các câu)."""
    words = sum(len(normalize_words(s["text"])) for s in segments)
    seconds = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in segments)
    if not words or seconds <= 0:
        return None
    return round(words / seconds * 60, 1)


def segment_wpm(segment: dict) -> float | None:
    return words_per_minute([segment])
