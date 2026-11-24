"""UC-71 (bước 1) — xuất INTERACTION của hệ thống sang định dạng huấn luyện.

Đặc tả UC-71 ghi rõ `[Defer]`: *"Với khóa luận, train trên SLAM là đủ; UC này để
hướng phát triển."* Script này vì thế **chỉ làm bước thu thập** — bước duy nhất
có thể làm đúng ngay hôm nay và cũng là bước chặn đường mọi thứ phía sau.

Nó KHÔNG huấn luyện gì cả, và cố tình không tự động nối vào `ml/`: fine-tune
trên vài trăm lượt trả lời sẽ phá mô hình đang chạy chứ không cải thiện nó.
Thay vào đó, script in ra một **báo cáo mức sẵn sàng** để biết còn thiếu bao nhiêu.

Chạy (từ backend/):
    python -m app.scripts.export_interactions --out ../ml/data/processed/system_sequences.jsonl

Định dạng đầu ra giống `sequences_subset.jsonl` của SLAM để `ml/` đọc lại được
mà không cần bộ nạp riêng:
    {"user": "<id>", "seq": [[item_idx, correct, split, format_code], ...]}
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.scripts._console import use_utf8_console
from app.core.database import SessionLocal
from app.models.interaction import Interaction, counted_interaction
from app.models.item import Item

#: Cùng bảng mã với `ml/config.py` — hai bên phải khớp, lệch là mô hình đọc sai cột.
FORMAT2CODE = {"reverse_tap": 0, "reverse_translate": 1, "listen": 2}
FORMAT_OTHER = 3
MODE_TO_FORMAT = {
    "quiz": "reverse_tap", "matching": "reverse_tap", "flashcard": "reverse_tap",
    "dkt_smart": "reverse_tap", "sm2": "reverse_tap",
    "srs_review": "reverse_tap", "weak_review": "reverse_tap",
    "typing": "reverse_translate", "cloze": "reverse_translate",
    "dictation": "listen",
}

#: Dưới các mức này thì fine-tune chắc chắn hại nhiều hơn lợi. Con số lấy theo
#: quy mô SLAM (2.593 người học · 2,6 triệu lượt) chia đi rất nhiều lần — đây là
#: ngưỡng TỐI THIỂU để nói chuyện, không phải mức lý tưởng.
MIN_USERS = 50
MIN_INTERACTIONS = 20_000
MIN_PER_USER = 50

#: Chia theo thời gian trong chuỗi của từng người: học trước -> train, sau -> dev/test.
#: Chia ngẫu nhiên là rò rỉ tương lai vào quá khứ, đúng lỗi mà preprocess SLAM
#: đã tránh.
TRAIN_RATIO, DEV_RATIO = 0.7, 0.15


def format_code(mode: str | None) -> int:
    return FORMAT2CODE.get(MODE_TO_FORMAT.get((mode or "").strip().lower(), ""), FORMAT_OTHER)


def collect(db: Session) -> dict[int, list[tuple[str, int, int]]]:
    """{user_id: [(word, correct, format_code)...]} theo thứ tự thời gian."""
    rows = db.execute(
        select(
            Interaction.user_id, Item.word, Interaction.is_correct,
            Interaction.exercise_format,
        )
        .join(Item, Item.id == Interaction.item_id)
        .where(counted_interaction())  # lượt bị loại không vào dữ liệu huấn luyện
        .order_by(Interaction.user_id, Interaction.answered_at)
    ).all()

    seqs: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for user_id, word, correct, fmt in rows:
        seqs[user_id].append((word, int(bool(correct)), format_code(fmt)))
    return seqs


def build_vocab(seqs: dict[int, list[tuple[str, int, int]]]) -> dict[str, int]:
    """Từ điển từ -> chỉ số. Chỉ để tương thích định dạng.

    Bản DKT feature-based KHÔNG dùng chỉ số này (đó là cả điểm của nó), nhưng
    định dạng file vẫn giữ cột item để đọc lại bằng cùng một bộ nạp.
    """
    vocab: dict[str, int] = {"<PAD>": 0, "<UNK>": 1}
    for seq in seqs.values():
        for word, _, _ in seq:
            vocab.setdefault(word, len(vocab))
    return vocab


def split_of(position: int, length: int) -> str:
    if position < int(length * TRAIN_RATIO):
        return "train"
    if position < int(length * (TRAIN_RATIO + DEV_RATIO)):
        return "dev"
    return "test"


def report(seqs: dict[int, list[tuple[str, int, int]]]) -> bool:
    """In mức sẵn sàng. Trả True nếu dữ liệu đủ để nói chuyện fine-tune."""
    usable = {u: s for u, s in seqs.items() if len(s) >= MIN_PER_USER}
    total = sum(len(s) for s in seqs.values())
    fmt_counts: dict[int, int] = defaultdict(int)
    for seq in seqs.values():
        for _, _, code in seq:
            fmt_counts[code] += 1

    print(f"\n{'=' * 58}\nMỨC SẴN SÀNG CHO UC-71")
    print(f"  người học có dữ liệu     : {len(seqs):,}")
    print(f"  người học >= {MIN_PER_USER} lượt      : {len(usable):,}  (cần {MIN_USERS:,})")
    print(f"  tổng lượt trả lời        : {total:,}  (cần {MIN_INTERACTIONS:,})")
    name = {0: "reverse_tap", 1: "reverse_translate", 2: "listen", 3: "other"}
    print("  phân bố dạng bài         : "
          + ", ".join(f"{name[k]}={v:,}" for k, v in sorted(fmt_counts.items())))

    ok = len(usable) >= MIN_USERS and total >= MIN_INTERACTIONS
    if ok:
        print("\n  ĐỦ để thử fine-tune. Vẫn phải đánh giá lại (UC-67) trước khi")
        print("  triển khai (UC-68) — dữ liệu đủ nhiều không có nghĩa là đủ tốt.")
    else:
        print("\n  CHƯA ĐỦ. Fine-tune lúc này sẽ phá mô hình đang chạy chứ không")
        print("  cải thiện nó: vài trăm lượt trả lời không đại diện cho ai cả.")
        print("  Giữ nguyên mô hình huấn luyện trên SLAM cho tới khi có người học thật.")
    print("=" * 58)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="file .jsonl đầu ra")
    parser.add_argument("--min-per-user", type=int, default=MIN_PER_USER)
    args = parser.parse_args()

    with SessionLocal() as db:
        seqs = collect(db)

    ready = report(seqs)

    kept = {u: s for u, s in seqs.items() if len(s) >= args.min_per_user}
    vocab = build_vocab(kept)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for user_id, seq in sorted(kept.items()):
            rows = [
                [vocab[word], correct, split_of(i, len(seq)), code]
                for i, (word, correct, code) in enumerate(seq)
            ]
            fh.write(json.dumps({"user": str(user_id), "seq": rows}, ensure_ascii=False) + "\n")

    vocab_path = args.out.with_name(args.out.stem + "_vocab.json")
    vocab_path.write_text(json.dumps(vocab, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"\nĐã ghi {len(kept):,} chuỗi -> {args.out}")
    print(f"Từ điển {len(vocab):,} mục -> {vocab_path}")
    if not ready:
        print("(Xuất ra để xem/kiểm được, KHÔNG có nghĩa là nên đem đi huấn luyện.)")


if __name__ == "__main__":
    use_utf8_console()
    main()
