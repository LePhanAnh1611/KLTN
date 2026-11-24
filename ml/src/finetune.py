"""UC-71 (bước 2) — fine-tune mô hình trên dữ liệu tương tác của hệ thống.

Đầu vào là file do `backend/app/scripts/export_interactions.py` xuất ra.

Ba nguyên tắc script này giữ, và chúng quan trọng hơn phần huấn luyện:

1. **Biết từ chối.** Dưới ngưỡng dữ liệu thì dừng hẳn. Fine-tune trên vài trăm
   lượt trả lời không cải thiện gì — nó chỉ kéo mô hình về phía một nhúm người
   dùng và phá thứ đã học từ 2,6 triệu lượt của SLAM.
2. **Không bao giờ ghi đè bản đang phục vụ.** Ghi ra `dkt_feat_finetuned_best.pt`.
   Đổi mô hình đang chạy là việc của con người, sau khi nhìn số (UC-67 -> UC-68).
3. **Đánh giá trên phần giữ lại theo THỜI GIAN** của chính dữ liệu hệ thống —
   người học sau này sẽ dùng mô hình để dự đoán tương lai, nên phải đo đúng như vậy.

Chạy (từ ml/):
    python src/finetune.py --data data/processed/system_sequences.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from src import dkt as _dkt  # noqa: E402
from src.dkt_feat import (  # noqa: E402
    FeatureDKT,
    HistoryWindowDataset,
    _batch_feats,
    _scored,
    collate_history,
    run_eval,
)
from src.features import FEATURE_DIM, build_matrix  # noqa: E402
from src.history_features import HISTORY_DIM  # noqa: E402

#: Khớp với ngưỡng trong `export_interactions.py`. Hai chỗ phải giống nhau, nếu
#: không thì bên xuất bảo "chưa đủ" mà bên train vẫn chạy.
MIN_USERS = 50
MIN_INTERACTIONS = 20_000

#: Learning rate thấp hơn hẳn lúc train từ đầu: đây là *chỉnh nhẹ* một mô hình
#: đã học tốt, không phải học lại từ đầu trên tập nhỏ.
FINETUNE_LR = 1e-4


def load_system_data(path: Path) -> tuple[dict, dict[str, int]]:
    """Đọc file xuất từ backend + từ điển đi kèm."""
    vocab_path = path.with_name(path.stem + "_vocab.json")
    if not path.exists() or not vocab_path.exists():
        sys.exit(
            f"Chưa có {path.name} / {vocab_path.name}. Xuất trước:\n"
            "  cd backend && python -m app.scripts.export_interactions "
            f"--out ../ml/{path.relative_to(Path.cwd()) if path.is_absolute() else path}"
        )

    code = config.SPLIT2CODE
    data: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            seq = row["seq"]
            data[row["user"]] = {
                "items": np.array([t[0] for t in seq], dtype=np.int64),
                "corrects": np.array([t[1] for t in seq], dtype=np.int64),
                "splits": np.array([code[t[2]] for t in seq], dtype=np.int64),
                "formats": np.array(
                    [t[3] if len(t) > 3 else config.FORMAT_OTHER for t in seq],
                    dtype=np.int64,
                ),
            }
    return data, json.loads(vocab_path.read_text(encoding="utf-8"))


def gate(data: dict) -> None:
    """Dừng hẳn nếu dữ liệu chưa đủ. Đây là phần quan trọng nhất của script."""
    users = len(data)
    total = sum(len(v["items"]) for v in data.values())
    print(f"Dữ liệu hệ thống: {users:,} người học · {total:,} lượt trả lời")
    if users >= MIN_USERS and total >= MIN_INTERACTIONS:
        return

    print(
        f"\nDỪNG — cần tối thiểu {MIN_USERS:,} người học và {MIN_INTERACTIONS:,} lượt.\n"
        "Fine-tune trên tập nhỏ hơn thế không cải thiện gì: nó kéo mô hình về phía\n"
        "một nhúm người dùng và phá thứ đã học từ 2,6 triệu lượt của SLAM.\n"
        "Giữ nguyên mô hình huấn luyện trên SLAM cho tới khi có đủ người học thật."
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path,
                        default=config.PROCESSED_DIR / "system_sequences.jsonl")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--force", action="store_true",
                        help="bỏ qua chốt chặn dữ liệu (chỉ để thử nghiệm, KHÔNG để triển khai)")
    args = parser.parse_args()

    config.set_seed()
    data, vocab = load_system_data(args.data)
    if not args.force:
        gate(data)
    else:
        print("CẢNH BÁO: đã bỏ qua chốt chặn dữ liệu (--force). Kết quả KHÔNG dùng để triển khai.")

    base_ckpt = config.MODELS_DIR / "dkt_feat_best.pt"
    if not base_ckpt.exists():
        sys.exit(f"Chưa có mô hình nền {base_ckpt} — train trên SLAM trước.")
    ckpt = torch.load(base_ckpt, map_location="cpu", weights_only=False)
    cfg = ckpt.get("config", config.CONFIG)
    n_feat = ckpt["feature_dim"]

    expected = FEATURE_DIM + HISTORY_DIM + config.FORMAT_DIM
    if n_feat != expected:
        sys.exit(
            f"Mô hình nền có {n_feat} chiều nhưng bộ tính đặc trưng sinh ra {expected}. "
            "Train lại trên SLAM trước khi fine-tune."
        )

    # Bảng đặc trưng dựng từ TỪ THẬT của hệ thống (không phải token SLAM) — đây
    # chính là chỗ bản feature-based làm được mà bản theo ID thì không.
    tokens = [""] * len(vocab)
    for word, idx in vocab.items():
        tokens[idx] = "" if word.startswith("<") else word
    table = torch.from_numpy(build_matrix(tokens))

    _dkt.VOCAB = len(vocab)
    _dkt.PAD_INPUT = 2 * len(vocab)

    ds = HistoryWindowDataset(data, cfg["max_seq_len"], cfg["stride"])
    loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=True,
                        collate_fn=collate_history)
    eval_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=False,
                             collate_fn=collate_history)

    model = FeatureDKT(n_feat, cfg["embedding_dim"], cfg["hidden_dim"],
                       cfg["num_layers"], cfg["dropout"])
    model.load_state_dict(ckpt["state_dict"])
    device = torch.device("cpu")

    before = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["test"], True)
    print(f"\nTRƯỚC fine-tune — test-AUC trên dữ liệu hệ thống: {before['auc']:.4f} "
          f"(n={before['n']:,})")

    opt = torch.optim.Adam(model.parameters(), lr=FINETUNE_LR)
    bce = nn.BCEWithLogitsLoss()
    for epoch in range(1, args.epochs + 1):
        model.train()
        for batch in loader:
            corrects = batch[2]; splits = batch[3]; cand = batch[4]
            logit = model(_batch_feats(batch, table, device, True), corrects)
            g, t = _scored(logit, corrects, splits, cand, config.SPLIT2CODE["train"])
            if g.numel() == 0:
                continue
            loss = bce(g, t)
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip"])
            opt.step()
        metrics = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["test"], True)
        print(f"  epoch {epoch} test-AUC={metrics['auc']:.4f}")

    after = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["test"], True)
    out = config.MODELS_DIR / "dkt_feat_finetuned_best.pt"
    torch.save({
        "state_dict": model.state_dict(), "config": cfg,
        "feature_dim": n_feat, "use_history": True, "model": "dkt_feat_finetuned",
    }, out)

    print(f"\nSAU fine-tune  — test-AUC: {after['auc']:.4f}")
    print(f"Đã ghi {out}")
    print(
        "\nKHÔNG tự triển khai. Nhìn hai con số trên rồi quyết:\n"
        "  - tốt hơn rõ rệt  -> đổi tên thành dkt_feat_best.pt và dựng lại ml-serve;\n"
        "  - không hơn       -> giữ nguyên bản SLAM, dữ liệu chưa nói được gì.\n"
        "Nhớ chạy `python -m src.serve_feat` sau khi đổi để chắc không lệch train/serve."
    )


if __name__ == "__main__":
    config.use_utf8_console()
    main()
