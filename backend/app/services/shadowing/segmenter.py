"""Gộp mảnh phụ đề thành CÂU LUYỆN cho shadowing.

Phụ đề YouTube là các mảnh 2–3 giây cắt ngang câu ("so today we're going to" /
"talk about the weather"). Nhại lại một mảnh như vậy vô nghĩa, nên phải gộp:

1. Làm sạch: bỏ chú thích [Music], (applause), dấu >> đổi người nói, xuống dòng.
2. Sửa chồng lấn: phụ đề tự động hay có mảnh kéo dài qua mốc bắt đầu của mảnh
   sau — cắt `end` về `start` của mảnh kế tiếp.
3. Gộp tham lam, ngắt khi một trong các điều kiện xảy ra:
   - câu hiện tại kết thúc bằng dấu kết câu VÀ đã dài ≥ MIN_SEC;
   - khoảng lặng tới mảnh sau > MAX_GAP_SEC (người nói đã ngừng);
   - thêm mảnh sau sẽ vượt MAX_SEC (dài quá thì khó nhại);
   - phụ đề KHÔNG có dấu câu (tự động) và câu đã dài ≥ TARGET_SEC.
4. Câu quá ngắn (< MIN_WORDS từ) nhập vào câu bên cạnh nếu không vượt MAX_SEC.

Các hằng số là tham số của thuật toán cắt, không phải ngưỡng nghiệp vụ, nên để
ở đây cùng test thay vì bảng cấu hình.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.shadowing import Snippet

MIN_SEC = 2.5
TARGET_SEC = 6.0
MAX_SEC = 12.0
MAX_GAP_SEC = 1.2
MIN_WORDS = 3

_ANNOTATION = re.compile(r"\[[^\]]*\]|\([^)]*\)|♪+")
_SPEAKER = re.compile(r"^\s*(>>|-)\s*")
_SPACES = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"[.!?…][\"')\]]*$")


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "text": self.text,
        }


def clean_text(text: str) -> str:
    """Bỏ chú thích không phải lời nói, chuẩn hóa khoảng trắng."""
    text = text.replace("\n", " ")
    text = _ANNOTATION.sub(" ", text)
    text = _SPEAKER.sub("", text)
    text = text.replace(">>", " ")
    return _SPACES.sub(" ", text).strip()


def _has_punctuation(snippets: list[Snippet]) -> bool:
    """Phụ đề tự động gần như không có dấu kết câu; dùng để chọn cách ngắt."""
    ends = sum(1 for s in snippets if _SENTENCE_END.search(s.text.strip()))
    return ends >= max(1, len(snippets) // 10)


def segment(snippets: list[Snippet]) -> list[Segment]:
    """Gộp mảnh phụ đề thành danh sách câu luyện, đánh số lại từ 0."""
    cleaned: list[tuple[str, float, float]] = []
    ordered = sorted(snippets, key=lambda s: s.start)
    for i, snip in enumerate(ordered):
        text = clean_text(snip.text)
        if not text:
            continue
        end = snip.start + max(snip.duration, 0.0)
        if i + 1 < len(ordered) and ordered[i + 1].start > snip.start:
            end = min(end, ordered[i + 1].start)
        if end <= snip.start:
            end = snip.start + 0.5
        cleaned.append((text, snip.start, end))

    if not cleaned:
        return []

    punctuated = _has_punctuation([Snippet(t, s, e - s) for t, s, e in cleaned])

    merged: list[Segment] = []
    current: Segment | None = None
    for text, start, end in cleaned:
        if current is None:
            current = Segment(index=0, start=start, end=end, text=text)
            continue

        gap = start - current.end
        would_be = end - current.start
        finished = punctuated and bool(_SENTENCE_END.search(current.text)) \
            and current.duration >= MIN_SEC
        long_enough = (not punctuated) and current.duration >= TARGET_SEC

        if finished or long_enough or gap > MAX_GAP_SEC or would_be > MAX_SEC:
            merged.append(current)
            current = Segment(index=0, start=start, end=end, text=text)
        else:
            current.text = f"{current.text} {text}"
            current.end = end
    if current is not None:
        merged.append(current)

    merged = _absorb_short(merged)
    for i, seg in enumerate(merged):
        seg.index = i
    return merged


def _absorb_short(segments: list[Segment]) -> list[Segment]:
    """Nhập câu dưới MIN_WORDS từ vào câu trước (hoặc sau) nếu không quá dài."""
    result: list[Segment] = []
    pending: Segment | None = None  # câu ngắn ở đầu, chờ nhập vào câu sau
    for seg in segments:
        if pending is not None:
            if seg.end - pending.start <= MAX_SEC:
                seg = Segment(seg.index, pending.start, seg.end, f"{pending.text} {seg.text}")
            else:
                result.append(pending)
            pending = None

        if seg.word_count < MIN_WORDS:
            if result and seg.end - result[-1].start <= MAX_SEC:
                prev = result[-1]
                prev.text = f"{prev.text} {seg.text}"
                prev.end = seg.end
                continue
            if not result:
                pending = seg
                continue
        result.append(seg)
    if pending is not None:
        result.append(pending)
    return result


def normalize_edited(raw: list[dict]) -> list[Segment]:
    """Kiểm và chuẩn hóa danh sách câu do admin sửa tay.

    Giữ thứ tự theo `start`, bỏ câu rỗng, đánh số lại. Mốc sai (end ≤ start)
    là lỗi của người sửa — báo ra thay vì tự đoán.
    """
    items: list[Segment] = []
    for row in raw:
        text = clean_text(str(row.get("text", "")))
        start = float(row["start"])
        end = float(row["end"])
        if not text:
            continue
        if start < 0 or end <= start:
            raise ValueError(f"Câu “{text[:40]}” có mốc thời gian không hợp lệ ({start} → {end}).")
        items.append(Segment(index=0, start=start, end=end, text=text))
    items.sort(key=lambda s: s.start)
    for i, seg in enumerate(items):
        seg.index = i
    return items
