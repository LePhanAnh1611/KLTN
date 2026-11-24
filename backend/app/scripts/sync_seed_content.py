"""Đồng bộ NỘI DUNG bộ từ nền (data/vocab_seed_core.json) vào DB đang chạy — bug #8/#9.

    python -m app.scripts.sync_seed_content            # chạy thử: chỉ in ra sẽ đổi gì
    python -m app.scripts.sync_seed_content --apply    # ghi thật

Vì sao cần: item trong DB là BẢN SAO của JSON lúc seed. Dựng lại bộ nền (sửa
phiên âm, sửa nghĩa/từ loại) không đụng gì tới DB — pilot vẫn hiện "main = cuộc
chọi gà" dù JSON đã sửa từ lâu. `seed_demo`/`sync_roadmap` chỉ TẠO bộ còn thiếu,
không cập nhật bộ đã có.

Phạm vi — chỉ nội dung hệ thống, không đụng chữ người học:
  - Bộ gốc: bộ công khai, `origin_set_id` NULL, tên trùng tên một bộ trong JSON.
  - Bản sao người học đã tải về (`origin_set_id` -> bộ gốc, Q1).
  - Khớp item theo `word`; bỏ item người học tự nhập/tự sửa nghĩa
    (`meaning_source` NULL hoặc 'user').
  - Ở bản sao: trường nào người học đã sửa riêng (khác bản gốc TRƯỚC khi đồng
    bộ) thì giữ nguyên trường đó.

Cập nhật TẠI CHỖ, KHÔNG theo Q6 (sửa từ đã có lịch sử -> tạo item mới): đây là
sửa lỗi dữ liệu của CÙNG một từ, nên Interaction / KnowledgeState / ReviewSchedule
giữ nguyên — người học không mất mastery và lịch ôn của ~1.000 từ.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.word_set import WordSet

CORE_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "vocab_seed_core.json"

#: Trường nội dung đồng bộ từ JSON. `word` là khóa khớp nên không nằm ở đây.
FIELDS = (
    "phonetic", "meaning", "part_of_speech",
    "meaning_source", "meaning_confidence", "example", "example_source",
    # Đứng SAU `example`: bản dịch chỉ ghi khi câu ví dụ của item (đã đồng bộ ở
    # trên) đúng là câu mà bản dịch này dịch — xem `_translation_fits`.
    "example_vi",
)


def _translation_fits(item: Item, record: dict) -> bool:
    """Người học tự sửa câu ví dụ ở bản sao -> bản dịch của câu gốc không còn khớp."""
    return _norm(item.example) == _norm(record.get("example"))


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _system_content(item: Item) -> bool:
    return item.meaning_source not in (None, "user")


def _live_items(db: Session, word_set_id: int) -> list[Item]:
    return list(db.execute(
        select(Item).where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalars())


def sync_seed_content(db: Session, payload: dict, *, apply: bool) -> Counter[str]:
    """Đồng bộ và trả về thống kê. `apply=False` thì rollback, không ghi gì."""
    specs = {spec["name"]: {it["word"]: it for it in spec["items"]}
             for spec in payload["word_sets"]}
    stats: Counter[str] = Counter()

    originals = db.execute(select(WordSet).where(
        WordSet.origin_set_id.is_(None), WordSet.is_public.is_(True),
        WordSet.deleted_at.is_(None), WordSet.name.in_(list(specs)),
    )).scalars().all()

    for original in originals:
        spec = specs[original.name]
        stats["bộ gốc"] += 1
        source_items = {it.word: it for it in _live_items(db, original.id)}
        # Ảnh chụp bản gốc TRƯỚC khi sửa: để nhận ra trường nào ở bản sao người
        # học đã tự sửa (khác bản gốc) mà giữ lại.
        before = {w: {f: _norm(getattr(it, f)) for f in FIELDS} for w, it in source_items.items()}

        copies = db.execute(select(WordSet).where(
            WordSet.origin_set_id == original.id, WordSet.deleted_at.is_(None),
        )).scalars().all()
        targets: list[tuple[Item, dict | None]] = [(it, None) for it in source_items.values()]
        for copy in copies:
            stats["bản sao"] += 1
            targets += [(it, before.get(it.word)) for it in _live_items(db, copy.id)]

        for item, base in targets:
            record = spec.get(item.word)
            if record is None or not _system_content(item):
                continue
            changed = False
            for field in FIELDS:
                new, old = _norm(record.get(field)), _norm(getattr(item, field))
                if new == old:
                    continue
                if field == "example_vi" and not _translation_fits(item, record):
                    continue
                if base is not None and old != base.get(field, old):
                    stats["giữ chỗ người học tự sửa"] += 1
                    continue
                setattr(item, field, record.get(field) or None)
                stats[f"đổi {field}"] += 1
                changed = True
            stats["item cập nhật"] += changed

    if apply:
        db.commit()
    else:
        db.rollback()
    return stats


def main() -> None:
    from app.core.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="ghi thật (mặc định chỉ chạy thử)")
    parser.add_argument("--seed", type=Path, default=CORE_SEED_PATH)
    args = parser.parse_args()

    payload = json.loads(args.seed.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        stats = sync_seed_content(db, payload, apply=args.apply)
    print("ĐÃ GHI" if args.apply else "CHẠY THỬ — chưa ghi gì (thêm --apply để ghi)")
    for key, value in sorted(stats.items()):
        print(f"  {key:<28} {value:>7,}")


if __name__ == "__main__":
    from app.scripts._console import use_utf8_console

    use_utf8_console()
    main()
