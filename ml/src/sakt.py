"""Giai đoạn 3.5 — SAKT (Self-Attentive Knowledge Tracing) trên SLAM en_es.

Chạy: (từ ml/)
    python src/sakt.py --subset            # debug 300 user
    python src/sakt.py --full              # train full, early stopping dev-AUC

Tái dùng KHUNG DKT: WindowDataset, collate, _gather_preds (next-step + mask
score_from cho cả eval), run_eval, evaluate() chung -> so sánh công bằng.
Khác DKT ở chỗ encode chuỗi: self-attention (Transformer) có MASK NHÂN QUẢ
thay cho LSTM.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import src.dkt as dkt  # tái dùng Dataset/collate/eval/loaders  # noqa: E402
from src.evaluate import evaluate  # noqa: E402


class SAKT(nn.Module):
    """Encoder self-attention: emb(2*item+correct) + positional -> attention nhân quả
    -> Linear -> logits P(correct) cho mọi item. Giữ next-step gather như DKT."""

    def __init__(self, vocab, d_model, nhead, dim_ff, dropout, max_len):
        super().__init__()
        self.emb = nn.Embedding(2 * vocab + 1, d_model, padding_idx=2 * vocab)
        self.pos = nn.Embedding(max_len, d_model)
        self.drop = nn.Dropout(dropout)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_ff,
            dropout=dropout, batch_first=True, norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.out = nn.Linear(d_model, vocab)
        self.pad_input = 2 * vocab

    def forward(self, inp):
        B, L = inp.shape
        pos_ids = torch.arange(L, device=inp.device).unsqueeze(0).expand(B, L)
        x = self.drop(self.emb(inp) + self.pos(pos_ids))
        # mask nhân quả: vị trí t chỉ nhìn [0..t] (True = chặn)
        causal = torch.triu(torch.ones(L, L, device=inp.device, dtype=torch.bool), diagonal=1)
        pad_mask = inp == self.pad_input  # (B, L) True ở bước đệm
        h = self.encoder(x, mask=causal, src_key_padding_mask=pad_mask)
        return self.out(self.drop(h))  # logits (B, L, vocab)


def train(subset: bool, tag: str) -> tuple[dict, dict | None]:
    cfg = config.CONFIG
    config.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
    vocab = len(item2idx)
    # đồng bộ hằng số PAD cho collate của dkt
    dkt.VOCAB = vocab
    dkt.PAD_INPUT = 2 * vocab

    data = dkt.load_sequences(subset)
    ds = dkt.WindowDataset(data, cfg["max_seq_len"], cfg["stride"])
    g = torch.Generator(); g.manual_seed(config.SEED)
    train_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=True,
                              collate_fn=dkt.collate, generator=g)
    eval_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=False,
                             collate_fn=dkt.collate)

    model = SAKT(vocab, cfg["embedding_dim"], cfg["nhead"], cfg["dim_feedforward"],
                 cfg["dropout"], cfg["max_seq_len"]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"])
    bce = nn.BCEWithLogitsLoss()

    best_dev = -1.0; best_state = None; best_epoch = -1; no_improve = 0
    t0 = time.time()
    print(f"[SAKT/{tag}] users={len(data)} windows={len(ds)} vocab={vocab} device={device.type}")
    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        total_loss = 0.0; nb = 0
        for inp, items, corrects, splits, cand in train_loader:
            inp = inp.to(device); items = items.to(device)
            corrects = corrects.to(device); splits = splits.to(device); cand = cand.to(device)
            logits = model(inp)
            g_logit, target = dkt._gather_preds(logits, items, corrects, splits, cand,
                                                config.SPLIT2CODE["train"])
            if g_logit.numel() == 0:
                continue
            loss = bce(g_logit, target)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip"])
            opt.step()
            total_loss += loss.item(); nb += 1

        tr = dkt.run_eval(model, eval_loader, device, config.SPLIT2CODE["train"])
        dv = dkt.run_eval(model, eval_loader, device, config.SPLIT2CODE["dev"])
        print(f"  epoch {epoch:2d} | loss {total_loss/max(nb,1):.4f} | "
              f"train-AUC {tr['auc']:.4f} | dev-AUC {dv['auc']:.4f} | {time.time()-t0:.0f}s")

        if dv["auc"] > best_dev:
            best_dev = dv["auc"]; best_epoch = epoch; no_improve = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            no_improve += 1
            if no_improve >= cfg["patience"]:
                print(f"  early stop (patience {cfg['patience']}) @ epoch {epoch}")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    test = dkt.run_eval(model, eval_loader, device, config.SPLIT2CODE["test"])
    elapsed = round(time.time() - t0, 1)
    print(f"[SAKT/{tag}] BEST dev-AUC {best_dev:.4f} @ep{best_epoch} | "
          f"TEST AUC {test['auc']:.4f} ACC {test['accuracy']:.4f} n={test['n']:,} | {elapsed}s")

    metrics = {
        "auc": test["auc"], "accuracy": test["accuracy"], "n": test["n"],
        "best_dev_auc": best_dev, "best_epoch": best_epoch,
        "n_users": len(data), "n_windows": len(ds),
        "d_model": cfg["embedding_dim"], "nhead": cfg["nhead"],
        "epochs_run": epoch, "time_s": elapsed,
    }
    return metrics, best_state


def save_results(key: str, metrics: dict) -> None:
    path = config.MODELS_DIR / "results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.setdefault("sakt", {})[key] = metrics
    path.write_text(json.dumps(allr, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Đã lưu", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    if args.full:
        metrics, best_state = train(subset=False, tag="full")
        if best_state is not None:
            torch.save({"state_dict": best_state, "config": config.CONFIG,
                        "metrics": metrics}, config.MODELS_DIR / "sakt_best.pt")
        save_results("full", metrics)
    else:
        metrics, _ = train(subset=True, tag="subset")
        save_results("subset", metrics)


if __name__ == "__main__":
    main()
