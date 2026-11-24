"""Giai đoạn 3.2 — Tiền xử lý SLAM en_es -> dữ liệu Knowledge Tracing.

Chạy: (từ thư mục ml/)  python src/preprocess.py

Ràng buộc (xem kế hoạch đã duyệt):
- item2idx CHỈ từ train; token lạ ở dev/test -> <UNK> (không thêm item mới).
- Chuỗi theo thứ tự thời gian mỗi user; gộp train -> dev -> test (dev/test là
  tương lai của chính user, nối tiếp lịch sử train làm ngữ cảnh — không cold-start,
  không rò tương lai vì LSTM nhân quả).
- Giữ ranh giới split; mỗi phần tử mang cờ split (0=train,1=dev,2=test).
- correct = 1 - label (label=1 nghĩa là trả lời SAI).
- Cắt/segment bằng sliding window để dành lúc train (hàm iter_windows), lưu chuỗi đầy đủ.
"""
from __future__ import annotations

import json
import pickle
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # để import config từ ml/
import config  # noqa: E402


def iter_interactions(
    data_path: Path, key_path: Path | None = None
) -> Iterator[tuple[str, str, int | None, float, str]]:
    """Yield (user, token, label, days, exercise_format) theo thứ tự dòng trong file.

    label: cột 7 ở train; dev/test lấy từ key_path (None nếu instance_id không khớp).

    `exercise_format` lấy từ dòng metadata `# ... format:...` — SLAM ghi sẵn ba
    dạng bài (`reverse_tap`, `reverse_translate`, `listen`). Đây là tín hiệu thật
    sự có ích: trả lời đúng một bài "chạm vào ô đáp án có sẵn" không chứng minh
    mức nắm vững bằng tự gõ lại cả từ.
    """
    labels: dict[str, int] = {}
    if key_path is not None:
        with open(key_path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2:
                    labels[parts[0]] = int(parts[1])

    user: str | None = None
    days = 0.0
    fmt = ""
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#"):
                if "user:" in line:  # dòng metadata bài tập
                    meta = {}
                    for p in line.lstrip("#").split():
                        if ":" in p:
                            k, v = p.split(":", 1)
                            meta[k] = v
                    user = meta.get("user")
                    days = float(meta.get("days", 0) or 0)
                    fmt = meta.get("format", "")
                continue  # dòng '# prompt:' -> bỏ qua
            if not line.strip():
                continue
            parts = line.split()
            instance_id, token = parts[0], parts[1]
            if len(parts) >= 7:
                label: int | None = int(float(parts[6]))
            else:
                label = labels.get(instance_id)  # có thể None nếu thiếu key
            yield user, token, label, days, fmt


def norm_token(token: str) -> str:
    return token.lower() if config.CONFIG["lowercase_tokens"] else token


def preprocess() -> None:
    config.set_seed()
    base = config.SLAM_DIR / config.SLAM_BASE
    lowercase = config.CONFIG["lowercase_tokens"]

    item2idx: dict[str, int] = {"<PAD>": config.PAD_IDX, "<UNK>": config.UNK_IDX}
    sequences: dict[str, dict[str, list[int]]] = {}
    # theo dõi khoảng days mỗi user theo split để sanity-check thứ tự thời gian
    day_range: dict[str, dict[int, list[float]]] = defaultdict(dict)

    stats = {
        "interactions": {"train": 0, "dev": 0, "test": 0},
        "unk": {"dev": 0, "test": 0},
        "missing_label": {"dev": 0, "test": 0},
    }
    train_users: set[str] = set()

    def add(user: str, idx: int, correct: int, split: str, days: float,
            fmt: str = "") -> None:
        seq = sequences.setdefault(
            user,
            {"items": [], "corrects": [], "splits": [], "formats": [], "days": []},
        )
        seq["items"].append(idx)
        seq["corrects"].append(correct)
        seq["splits"].append(config.SPLIT2CODE[split])
        seq["formats"].append(config.FORMAT2CODE.get(fmt, config.FORMAT_OTHER))
        # `days` (số ngày kể từ khi vào khóa) trước đây chỉ dùng để sanity-check
        # thứ tự thời gian rồi vứt đi. Nay GIỮ LẠI: nó là thứ duy nhất trong SLAM
        # cho biết một từ đã bị bỏ quên bao lâu — mà quên là chuyện của thời gian
        # thực, không phải của số bước trong chuỗi.
        seq["days"].append(days)
        code = config.SPLIT2CODE[split]
        dr = day_range[user]
        if code not in dr:
            dr[code] = [days, days]
        else:
            dr[code][0] = min(dr[code][0], days)
            dr[code][1] = max(dr[code][1], days)

    # ---- TRAIN: xây item2idx + chuỗi (token train luôn có nhãn) ----
    for user, token, label, days, fmt in iter_interactions(Path(f"{base}.train")):
        token = norm_token(token)
        if token not in item2idx:
            item2idx[token] = len(item2idx)
        add(user, item2idx[token], 1 - label, "train", days, fmt)
        train_users.add(user)
        stats["interactions"]["train"] += 1

    # ---- DEV / TEST: map qua item2idx (token lạ -> UNK), nối tiếp lịch sử ----
    for split in ("dev", "test"):
        for user, token, label, days, fmt in iter_interactions(
            Path(f"{base}.{split}"), Path(f"{base}.{split}.key")
        ):
            if label is None:  # thiếu nhãn -> không dùng được, loại
                stats["missing_label"][split] += 1
                continue
            token = norm_token(token)
            idx = item2idx.get(token, config.UNK_IDX)
            if idx == config.UNK_IDX:
                stats["unk"][split] += 1
            add(user, idx, 1 - label, split, days, fmt)
            stats["interactions"][split] += 1

    # ---- Sanity checks ----
    order_violations = 0
    for user, dr in day_range.items():
        # thứ tự thời gian giữa các split: max(train) <= min(dev) <= min(test)
        tr = dr.get(config.SPLIT2CODE["train"])
        dv = dr.get(config.SPLIT2CODE["dev"])
        te = dr.get(config.SPLIT2CODE["test"])
        if tr and dv and tr[1] > dv[0]:
            order_violations += 1
        elif dv and te and dv[1] > te[0]:
            order_violations += 1
    cold_start_users = [u for u in sequences if u not in train_users]

    # ---- Lưu output ----
    out = config.PROCESSED_DIR
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "item2idx.json", "w", encoding="utf-8") as f:
        json.dump(item2idx, f, ensure_ascii=False, indent=0)

    packed = {
        user: {
            "items": np.asarray(seq["items"], dtype=np.int32),
            "corrects": np.asarray(seq["corrects"], dtype=np.int8),
            "splits": np.asarray(seq["splits"], dtype=np.int8),
            "formats": np.asarray(seq["formats"], dtype=np.int8),
            "days": np.asarray(seq["days"], dtype=np.float32),
        }
        for user, seq in sequences.items()
    }
    with open(out / "sequences.pkl", "wb") as f:
        pickle.dump(packed, f, protocol=pickle.HIGHEST_PROTOCOL)

    # subset debug (JSONL, dễ đọc bằng mắt) — lấy mẫu có seed
    code2split = {v: k for k, v in config.SPLIT2CODE.items()}
    users_sorted = sorted(sequences.keys())
    n_subset = min(config.CONFIG["subset_users"], len(users_sorted))
    subset = random.sample(users_sorted, n_subset)
    with open(out / "sequences_subset.jsonl", "w", encoding="utf-8") as f:
        for user in subset:
            seq = sequences[user]
            # Phần tử thứ 4 (mã dạng bài) thêm sau nên các loader cũ chỉ đọc 3
            # phần tử đầu vẫn chạy nguyên.
            triples = [
                [it, cr, code2split[sp], fm]
                for it, cr, sp, fm in zip(
                    seq["items"], seq["corrects"], seq["splits"], seq["formats"]
                )
            ]
            f.write(json.dumps({"user": user, "seq": triples}, ensure_ascii=False) + "\n")

    meta = {
        "seed": config.SEED,
        "lowercase_tokens": lowercase,
        "vocab_size": len(item2idx),
        "num_items_real": len(item2idx) - 2,  # trừ PAD, UNK
        "split_code": config.SPLIT2CODE,
        "users_total": len(sequences),
        "users_per_split": {
            s: sum(1 for u in sequences if config.SPLIT2CODE[s] in day_range[u])
            for s in ("train", "dev", "test")
        },
        "interactions": stats["interactions"],
        "interactions_total": sum(stats["interactions"].values()),
        "unk_interactions": stats["unk"],
        "missing_label_dropped": stats["missing_label"],
        "cold_start_users": len(cold_start_users),
        "time_order_violations": order_violations,
        "subset_users": n_subset,
        "config": {k: config.CONFIG[k] for k in ("max_seq_len", "stride", "subset_users")},
    }
    with open(out / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("=== Tiền xử lý xong ===")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("Đã lưu vào", out)


def iter_windows(n: int, max_len: int, stride: int) -> Iterator[tuple[int, int, int]]:
    """Sliding window cho lúc train (Giai đoạn 3.3).

    Yield (start, end, score_from) cho chuỗi dài n:
    - [start, end)   : cửa sổ đưa vào model (ngữ cảnh + phần chấm).
    - [score_from, end): các vị trí ĐƯỢC CHẤM (loss/metric) — phần "mới" so với
      cửa sổ trước; [start, score_from) là warm-up context. Mỗi vị trí được chấm
      đúng 1 lần; cửa sổ cuối luôn kết thúc ở n (phủ N interaction gần nhất).
    """
    if n <= max_len:
        yield 0, n, 0
        return
    start = 0
    prev_end = 0
    while True:
        end = min(start + max_len, n)
        score_from = 0 if start == 0 else prev_end
        yield start, end, score_from
        if end == n:
            break
        prev_end = end
        start += stride


if __name__ == "__main__":
    config.use_utf8_console()
    preprocess()
