"""Dựng bộ từ cho lộ trình v2 (UC-84 mở rộng) — HAI track song song mỗi level.

Run: python -m app.scripts.build_roadmap_v2
Ra:  data/vocab_seed_roadmap_v2.json  (đầu ra của script — KHÔNG sửa tay)

Vì sao có v2
------------
Lộ trình v1 cắt bộ NỀN theo thứ hạng tần suất, mỗi 50 từ một chặng
("A1 · Từ 1–50"…): có cơ sở tần suất, nhưng ranh giới 50 là tùy ý và từ trong
một chặng không liên quan gì tới nhau. v2 giữ trục LEVEL (CEFR) làm trục tiến
độ, và trong mỗi level chia hai track:

- Track CHỦ ĐỀ: từ có nhãn chủ đề trong CEFR-J Vocabulary Profile 1.5 — cột
  `Threshold` (Council of Europe, Threshold Level) ưu tiên, trống thì dùng
  `CoreInventory 1` (British Council/EAQUALS Core Inventory). Khớp theo
  (từ, từ loại), không chỉ theo mặt chữ — `can` (modal) không được nhận nhãn
  Shopping của danh từ `can` (cái lon).
- Track CỐT LÕI: các từ còn lại (từ chức năng, từ dùng chung, toàn bộ C1/C2),
  chia theo tần suất như v1.

Hai track RỜI NHAU và PHỦ ĐỦ: mỗi từ có CEFR của bộ nền nằm đúng một chặng v2
— không học trùng, DKT không thấy cùng một từ thành hai item.

Nhãn đã rà tay: nếu có `data/sources/LearningHub_Ra_nhan_chu_de.xlsx`, cột
"Chủ đề sửa" đè lên nhãn tự động; chọn "(Bỏ — …)" thì từ về track cốt lõi.

v1 KHÔNG bị đụng tới: script này chỉ ĐỌC `vocab_seed_core.json`.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CORE_PATH = DATA / "vocab_seed_core.json"
CEFRJ_PATH = DATA / "cefrj-vocabulary-profile-1.5.csv"
REVIEW_PATH = DATA / "sources" / "LearningHub_Ra_nhan_chu_de.xlsx"
OUT_PATH = DATA / "vocab_seed_roadmap_v2.json"

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
TOPIC_MIN = 15      # chủ đề ít hơn -> gom vào bộ "Tổng hợp chủ đề" của level
TOPIC_MAX = 40      # chủ đề nhiều hơn -> tách đều thành nhiều phần
CORE_SIZE = 50      # track cốt lõi: giữ cỡ chặng như v1
DROP_LABEL = "(Bỏ — chuyển về track cốt lõi)"
MIXED_TOPIC = "Tổng hợp chủ đề"

#: Nhãn Threshold Level -> chủ đề chung (tiếng Việt)
THRESHOLD = {
    "Personal identification": "Thông tin cá nhân",
    "House and home, environment": "Nhà cửa & môi trường",
    "Weather": "Nhà cửa & môi trường",
    "Daily life": "Sinh hoạt hằng ngày",
    "Free time, entertainment": "Giải trí & sở thích",
    "Travel": "Du lịch & địa điểm",
    "Places": "Du lịch & địa điểm",
    "Relations with other people": "Quan hệ xã hội",
    "Health and body care": "Sức khỏe & cơ thể",
    "Education": "Giáo dục & ngôn ngữ",
    "Language": "Giáo dục & ngôn ngữ",
    "Shopping": "Mua sắm & dịch vụ",
    "Services": "Mua sắm & dịch vụ",
    "Food and drink": "Ăn uống",
}
#: Nhãn Core Inventory -> cùng bộ chủ đề chung. Nhãn ngữ pháp/không phải chủ đề
#: (Collocation, Idiomatic expressions, Dimensions, Adjectives…) cố ý bỏ qua.
CORE_INVENTORY = {
    "Objects and rooms": "Nhà cửa & môi trường",
    "Things in the town, shops and shopping": "Mua sắm & dịch vụ",
    "Shopping": "Mua sắm & dịch vụ",
    "Clothes": "Mua sắm & dịch vụ",
    "Colours": "Mua sắm & dịch vụ",
    "Hobbies and pastimes": "Giải trí & sở thích",
    "Hobbies and lifestyles": "Giải trí & sở thích",
    "Leisure activities": "Giải trí & sở thích",
    "Media": "Giải trí & sở thích",
    "Film": "Giải trí & sở thích",
    "Arts": "Giải trí & sở thích",
    "Books and literature": "Giải trí & sở thích",
    "Holidays": "Giải trí & sở thích",
    "Food and drink": "Ăn uống",
    "Family life": "Quan hệ xã hội",
    "Personal information": "Thông tin cá nhân",
    "Nationalities and countries": "Thông tin cá nhân",
    "Ways of travelling": "Du lịch & địa điểm",
    "Ways of traveling": "Du lịch & địa điểm",
    "Travel and services vocab": "Du lịch & địa điểm",
    "Education": "Giáo dục & ngôn ngữ",
    "Work and Jobs": "Công việc",
    "Work and jobs": "Công việc",
    "News, lifestyles and current affairs": "Thời sự & xã hội",
    "Scientific development": "Thời sự & xã hội",
    "Technical and legal language": "Thời sự & xã hội",
}
TOPICS = sorted(set(THRESHOLD.values()) | set(CORE_INVENTORY.values()))

Key = tuple[str, str | None]   # (từ viết thường, từ loại)


def _cefrj_labels() -> dict[Key, tuple[str, str]]:
    """{(từ, từ loại): (nguồn, chủ đề chung)} — Threshold thắng Core Inventory."""
    threshold: dict[Key, tuple[str, str]] = {}
    inventory: dict[Key, tuple[str, str]] = {}
    with CEFRJ_PATH.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            for head in row["headword"].split("/"):
                key = (head.strip().lower(), row["pos"])
                if row["Threshold"] in THRESHOLD:
                    threshold.setdefault(key, ("threshold", THRESHOLD[row["Threshold"]]))
                if row["CoreInventory 1"] in CORE_INVENTORY:
                    inventory.setdefault(key, ("core_inventory", CORE_INVENTORY[row["CoreInventory 1"]]))
    return {**inventory, **threshold}


def _review_overrides() -> dict[tuple[str, str, str | None], str]:
    """{(level, từ, từ loại): chủ đề đã sửa tay} từ file rà nhãn (nếu có)."""
    if not REVIEW_PATH.exists():
        return {}
    import openpyxl   # requirements-import.txt — chỉ cần khi dựng lại dữ liệu

    sheet = openpyxl.load_workbook(REVIEW_PATH, read_only=True)["Rà nhãn"]
    rows = sheet.iter_rows(values_only=True)
    header = list(next(rows))
    col = {name: header.index(name) for name in ("Level", "Từ", "Từ loại", "Chủ đề sửa")}
    overrides = {}
    for row in rows:
        fixed = row[col["Chủ đề sửa"]]
        if not fixed:
            continue
        fixed = str(fixed).strip()
        if fixed != DROP_LABEL and fixed not in TOPICS:
            raise ValueError(f"Chủ đề không hợp lệ trong file rà nhãn: {fixed!r}")
        key = (row[col["Level"]], str(row[col["Từ"]]).lower(), row[col["Từ loại"]])
        overrides[key] = fixed
    return overrides


def _split(items: list[dict], size: int) -> list[list[dict]]:
    """Chia đều (không để phần cuối lèo tèo): 60 từ, tối đa 40 -> 30 + 30."""
    parts = max(1, math.ceil(len(items) / size))
    base, extra = divmod(len(items), parts)
    out, start = [], 0
    for i in range(parts):
        end = start + base + (1 if i < extra else 0)
        out.append(items[start:end])
        start = end
    return out


def build() -> dict:
    core = json.loads(CORE_PATH.read_text(encoding="utf-8"))
    labels = _cefrj_labels()
    overrides = _review_overrides()
    difficulty = {spec.get("cefr"): spec["difficulty"] for spec in core["word_sets"]}

    by_level: dict[str, list[dict]] = defaultdict(list)
    for spec in core["word_sets"]:
        for item in spec["items"]:
            if item.get("cefr") in LEVELS:
                by_level[item["cefr"]].append(item)

    stages: list[dict] = []
    stats: dict[str, dict] = {}
    for level in LEVELS:
        items = sorted(by_level[level], key=lambda it: it["rank"])
        topical: dict[str, list[dict]] = defaultdict(list)
        rest: list[dict] = []
        for item in items:
            key = (item["word"].lower(), item.get("part_of_speech"))
            auto = labels.get(key)
            fixed = overrides.get((level, *key))
            if fixed == DROP_LABEL:
                rest.append(item)
            elif fixed:
                topical[fixed].append({**item, "topic": fixed, "topic_source": "manual"})
            elif auto:
                topical[auto[1]].append({**item, "topic": auto[1], "topic_source": auto[0]})
            else:
                rest.append(item)

        level_stages: list[dict] = []
        pool: list[dict] = []
        for topic in TOPICS:
            words = topical.get(topic, [])
            if len(words) >= TOPIC_MIN:
                level_stages += _topic_stages(level, topic, words)
            else:
                pool += words
        if len(pool) >= TOPIC_MIN:
            level_stages += _topic_stages(level, MIXED_TOPIC, sorted(pool, key=lambda it: it["rank"]))
        else:
            # Quá ít để thành bộ riêng -> về track cốt lõi, KHÔNG bỏ từ nào
            rest += [{k: v for k, v in it.items() if k not in ("topic", "topic_source")} for it in pool]

        rest.sort(key=lambda it: it["rank"])
        for n, chunk in enumerate(_chunks(rest, CORE_SIZE), 1):
            level_stages.append(_stage(level, "core", None, f"Cốt lõi {n}", chunk))

        # Thứ tự trong level: tần suất trung bình tăng dần — một quy tắc duy
        # nhất cho cả hai track (từ phổ biến học trước, Nation 2001).
        level_stages.sort(key=lambda st: (st["mean_rank"], st["track"], st["title"]))
        for order, stage in enumerate(level_stages, 1):
            stage["order_index"] = order
            stage["difficulty"] = difficulty[level]
        stages += level_stages

        stats[level] = {
            "words": len(items),
            "topic_words": sum(len(s["items"]) for s in level_stages if s["track"] == "topic"),
            "topic_stages": sum(1 for s in level_stages if s["track"] == "topic"),
            "core_stages": sum(1 for s in level_stages if s["track"] == "core"),
        }

    _check_partition(by_level, stages)
    return {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "items": CORE_PATH.name,
            "topics": f"{CEFRJ_PATH.name} (Threshold ưu tiên, CoreInventory 1 dự phòng)",
            "review": REVIEW_PATH.name if REVIEW_PATH.exists() else None,
            "manual_overrides": len(overrides),
        },
        "rules": {"topic_min": TOPIC_MIN, "topic_max": TOPIC_MAX, "core_size": CORE_SIZE},
        "stats": stats,
        "stages": stages,
    }


def _chunks(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _topic_stages(level: str, topic: str, words: list[dict]) -> list[dict]:
    parts = _split(words, TOPIC_MAX)
    return [
        _stage(level, "topic", topic, topic if len(parts) == 1 else f"{topic} ({i}/{len(parts)})", part)
        for i, part in enumerate(parts, 1)
    ]


def _stage(level: str, track: str, topic: str | None, label: str, items: list[dict]) -> dict:
    return {
        "cefr": level,
        "track": track,
        "topic": topic,
        "title": f"{level} · {label}",
        # Tên bộ từ phải KHÁC tên bộ v1 ("A1 · Từ 1–50") — seed v1 tra bộ theo tên.
        "name": f"{level} · {'Chủ đề' if track == 'topic' else 'Lộ trình'} · {label}",
        "category": topic if track == "topic" else "Cốt lõi",
        "mean_rank": round(sum(it["rank"] for it in items) / len(items), 1),
        "items": items,
    }


def _check_partition(by_level: dict[str, list[dict]], stages: list[dict]) -> None:
    """Mỗi từ có CEFR nằm ĐÚNG MỘT chặng v2 — rời nhau và phủ đủ."""
    seen: dict[tuple, str] = {}
    for stage in stages:
        for it in stage["items"]:
            key = (stage["cefr"], it["word"].lower(), it.get("part_of_speech"))
            if key in seen:
                raise ValueError(f"Từ nằm ở hai chặng: {key} ({seen[key]}, {stage['title']})")
            seen[key] = stage["title"]
    expected = {(lv, it["word"].lower(), it.get("part_of_speech")) for lv, its in by_level.items() for it in its}
    if set(seen) != expected:
        raise ValueError(f"Lệch độ phủ: thiếu {len(expected - set(seen))}, thừa {len(set(seen) - expected)}")


def main() -> None:
    payload = build()
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT_PATH.name}: {len(payload['stages'])} stages")
    for level, s in payload["stats"].items():
        print(f"  {level}: {s['words']} từ — {s['topic_stages']} chặng chủ đề "
              f"({s['topic_words']} từ), {s['core_stages']} chặng cốt lõi")


if __name__ == "__main__":
    main()
