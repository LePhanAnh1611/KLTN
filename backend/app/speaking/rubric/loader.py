"""Nạp rubric TỪ CHÍNH `docs/speaking-rubric.md`.

Cố ý parse file markdown thay vì chép descriptor sang JSON: rubric là tài liệu
người thật đọc và sửa (mục 8 của chính nó yêu cầu calibrate rồi tinh chỉnh
descriptor). Nếu giữ hai bản, bản trong code sẽ lệch khỏi bản người ta sửa và
không ai biết. Ở đây markdown là nguồn sự thật DUY NHẤT cho descriptor + gợi ý
cải thiện; những thứ không có trong markdown (ngưỡng số, anchor example) nằm
riêng ở `thresholds.json` và `anchors.py`.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Thứ tự cố định — dùng làm khóa trong JSON đầu ra
CRITERIA = ("fluency", "pronunciation", "grammar_vocab", "coherence_task")

# Mã trong markdown (C1..C4) -> khóa máy dùng
_CODE_TO_KEY = {
    "C1": "fluency",
    "C2": "pronunciation",
    "C3": "grammar_vocab",
    "C4": "coherence_task",
}

_FILENAME = "speaking-rubric.md"

# Rubric nằm ở docs/ của repo, KHÔNG nằm trong package — cố ý, để nó là tài liệu
# người thật đọc và sửa. Hệ quả: đường dẫn khác nhau giữa lúc chạy tay và lúc
# chạy trong container (build context của backend không có docs/), nên phải dò
# vài chỗ thay vì tính cứng theo vị trí file.
def _candidates() -> list[Path]:
    here = Path(__file__).resolve()
    found: list[Path] = []

    override = os.getenv("SPEAKING_RUBRIC_PATH", "").strip()
    if override:
        found.append(Path(override))

    # Chạy tay: backend/app/speaking/rubric/ -> lên 4 cấp là gốc repo
    found.append(here.parents[4] / "docs" / _FILENAME)
    # Trong container: docs/ được mount vào /app/docs (xem docker-compose.yml)
    found.append(here.parents[3] / "docs" / _FILENAME)
    found.append(Path("/app/docs") / _FILENAME)
    return found


def resolve_rubric_path() -> Path | None:
    """Đường dẫn rubric đầu tiên tồn tại, None nếu không thấy chỗ nào."""
    return next((c for c in _candidates() if c.is_file()), None)


# Giữ tên cũ cho code/test đã dùng
RUBRIC_PATH = Path(__file__).resolve().parents[4] / "docs" / _FILENAME


@dataclass(frozen=True)
class LevelDescriptor:
    level: int
    label: str
    descriptor: str
    suggestion: str


@dataclass(frozen=True)
class Criterion:
    key: str
    code: str            # C1..C4
    name: str            # "Fluency (Độ trôi chảy)"
    levels: dict[int, LevelDescriptor]

    def at(self, level: int) -> LevelDescriptor:
        return self.levels[max(1, min(4, level))]


@dataclass(frozen=True)
class Rubric:
    version: str
    criteria: dict[str, Criterion]
    labels: dict[int, str]

    def label_of(self, level: int) -> str:
        return self.labels.get(max(1, min(4, level)), "")


def _clean(cell: str) -> str:
    """Bỏ nhấn mạnh markdown và khoảng trắng thừa trong một ô bảng."""
    return re.sub(r"\*+", "", cell).strip()


def _table_rows(block: str) -> list[list[str]]:
    """Các dòng dữ liệu của một bảng markdown (bỏ header và dòng phân cách)."""
    rows: list[list[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [_clean(c) for c in line.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue                      # dòng phân cách |---|---|
        rows.append(cells)
    return rows[1:] if rows else []       # bỏ dòng tiêu đề


def _parse_labels(text: str) -> dict[int, str]:
    """Mục 3 — thang bốn mức: | 1 | **Emerging** | ... |"""
    match = re.search(r"##\s*3\.[^\n]*\n(.*?)(?=\n---|\n##\s)", text, re.S)
    labels: dict[int, str] = {}
    if match:
        for cells in _table_rows(match.group(1)):
            if len(cells) >= 2 and cells[0].isdigit():
                labels[int(cells[0])] = cells[1]
    return labels


def _parse_criteria(text: str) -> dict[str, Criterion]:
    """Mục 4 — mỗi tiêu chí một bảng `### C1 — Fluency (...)`."""
    criteria: dict[str, Criterion] = {}

    pattern = re.compile(r"###\s*(C[1-4])\s*[—-]\s*(.+?)\n(.*?)(?=\n###\s|\n##\s|\Z)", re.S)
    for code, name, body in pattern.findall(text):
        key = _CODE_TO_KEY.get(code)
        if key is None:
            continue

        levels: dict[int, LevelDescriptor] = {}
        for cells in _table_rows(body):
            if len(cells) < 3:
                continue
            # ô mức có dạng "1 Emerging"
            head = cells[0].split(None, 1)
            if not head or not head[0].isdigit():
                continue
            level = int(head[0])
            levels[level] = LevelDescriptor(
                level=level,
                label=head[1].strip() if len(head) > 1 else "",
                descriptor=cells[1],
                suggestion=cells[2],
            )

        if len(levels) == 4:
            criteria[key] = Criterion(key=key, code=code, name=name.strip(), levels=levels)

    return criteria


def _parse_version(text: str) -> str:
    match = re.search(r"Version\s*([\d.]+)", text)
    return match.group(1) if match else "unknown"


@lru_cache(maxsize=4)
def load_rubric(path: str | None = None) -> Rubric:
    """Đọc & phân tích rubric. Kết quả được cache theo đường dẫn.

    Hỏng ở đây là hỏng cả module, nên báo lỗi to và rõ ngay lúc nạp thay vì để
    thiếu descriptor rồi chấm sai âm thầm.
    """
    if path:
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Không tìm thấy rubric tại {target}")
    else:
        target = resolve_rubric_path()
        if target is None:
            tried = "\n  - ".join(str(c) for c in _candidates())
            raise FileNotFoundError(
                "Không tìm thấy file rubric. Đã thử:\n  - " + tried
                + "\nĐặt biến môi trường SPEAKING_RUBRIC_PATH để trỏ tới file."
            )

    text = target.read_text(encoding="utf-8")
    labels = _parse_labels(text)
    criteria = _parse_criteria(text)

    missing = [c for c in CRITERIA if c not in criteria]
    if missing or len(labels) != 4:
        raise ValueError(
            f"Rubric không đọc được đầy đủ (thiếu tiêu chí: {missing}, "
            f"số mức đọc được: {len(labels)}). Kiểm tra định dạng bảng trong {target}."
        )

    return Rubric(version=_parse_version(text), criteria=criteria, labels=labels)
