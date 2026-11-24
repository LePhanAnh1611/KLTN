"""Giai đoạn 3.4 — DKT (Deep Knowledge Tracing, LSTM) trên SLAM en_es.

Chạy: (từ ml/)
    python src/dkt.py --subset            # debug 300 user, in train/dev AUC mỗi epoch
    python src/dkt.py --full              # train full, early stopping theo dev-AUC

DKT chuẩn (Piech 2015):
- input bước t = cặp (item, correct) -> embedding idx = 2*item + correct.
- output bước t = P(correct) cho MỌI item; chấm bước t+1 = gather output_t tại item_{t+1}.
- chống rò rỉ: loss CHỈ ở vị trí split=train; eval dev/test riêng; LSTM nhân quả.
- mỗi interaction chấm ĐÚNG 1 LẦN (mask score_from) cho cả loss lẫn eval.
- metric qua evaluate.evaluate() (dùng chung BKT) — AUC gộp toàn cục.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from src.preprocess import iter_windows  # noqa: E402

# `src.evaluate` cần scikit-learn — chỉ dùng khi HUẤN LUYỆN/ĐÁNH GIÁ. Service
# phục vụ (UC-68) chỉ import class DKT nên không kéo theo sklearn; nhờ vậy image
# ml-serve giữ được bộ phụ thuộc nhẹ (requirements-serve.txt).

VOCAB = None  # số item (gồm PAD, UNK) — set trong load
PAD_INPUT = None  # chỉ số input cho bước padding


# ---------------------------------------------------------------- data
def load_sequences(subset: bool) -> dict:
    if subset:
        code = config.SPLIT2CODE
        data = {}
        with open(config.PROCESSED_DIR / "sequences_subset.jsonl", encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                tr = o["seq"]
                data[o["user"]] = {
                    "items": np.array([t[0] for t in tr], dtype=np.int64),
                    "corrects": np.array([t[1] for t in tr], dtype=np.int64),
                    "splits": np.array([code[t[2]] for t in tr], dtype=np.int64),
                    # Phần tử thứ 4 thêm sau; file cũ không có -> coi như "other".
                    "formats": np.array(
                        [t[3] if len(t) > 3 else config.FORMAT_OTHER for t in tr],
                        dtype=np.int64,
                    ),
                }
        return data
    with open(config.PROCESSED_DIR / "sequences.pkl", "rb") as f:
        raw = pickle.load(f)
    return {
        u: {"items": v["items"].astype(np.int64),
            "corrects": v["corrects"].astype(np.int64),
            "splits": v["splits"].astype(np.int64),
            # File cũ chưa có cột này -> coi như "other" để loader không vỡ.
            "formats": (v["formats"].astype(np.int64) if "formats" in v
                        else np.full(len(v["items"]), config.FORMAT_OTHER, dtype=np.int64))}
        for u, v in raw.items()
    }


class WindowDataset(Dataset):
    """Mỗi sample = một cửa sổ (start,end,score_from) trên chuỗi 1 user."""

    def __init__(self, data: dict, max_len: int, stride: int):
        self.data = list(data.values())
        self.index = []  # (user_pos, start, end, score_from)
        for ui, seq in enumerate(self.data):
            n = len(seq["items"])
            for start, end, score_from in iter_windows(n, max_len, stride):
                self.index.append((ui, start, end, score_from))

    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        ui, start, end, score_from = self.index[i]
        seq = self.data[ui]
        items = seq["items"][start:end]
        corrects = seq["corrects"][start:end]
        splits = seq["splits"][start:end]
        W = end - start
        # candidate: vị trí p (local) được CHẤM (dự đoán từ p-1): p>=1 và p>=score_from_local
        score_from_local = score_from - start
        cand = np.zeros(W, dtype=bool)
        lo = max(score_from_local, 1)
        cand[lo:] = True
        inp = 2 * items + corrects  # chỉ số embedding cặp (item, correct)
        return (
            torch.from_numpy(inp),
            torch.from_numpy(items),
            torch.from_numpy(corrects),
            torch.from_numpy(splits),
            torch.from_numpy(cand),
        )


def collate(batch):
    lengths = [len(x[0]) for x in batch]
    Lmax = max(lengths)
    B = len(batch)
    inp = torch.full((B, Lmax), PAD_INPUT, dtype=torch.long)
    items = torch.zeros((B, Lmax), dtype=torch.long)
    corrects = torch.zeros((B, Lmax), dtype=torch.long)
    splits = torch.full((B, Lmax), -1, dtype=torch.long)
    cand = torch.zeros((B, Lmax), dtype=torch.bool)
    for i, (a, it, c, sp, cd) in enumerate(batch):
        L = len(a)
        inp[i, :L] = a; items[i, :L] = it; corrects[i, :L] = c
        splits[i, :L] = sp; cand[i, :L] = cd
    return inp, items, corrects, splits, cand


# ---------------------------------------------------------------- model
class DKT(nn.Module):
    def __init__(self, vocab, emb_dim, hidden, num_layers, dropout):
        super().__init__()
        self.emb = nn.Embedding(2 * vocab + 1, emb_dim, padding_idx=2 * vocab)
        self.drop = nn.Dropout(dropout)
        self.lstm = nn.LSTM(emb_dim, hidden, num_layers=num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.out = nn.Linear(hidden, vocab)

    def forward(self, inp):
        x = self.drop(self.emb(inp))
        h, _ = self.lstm(x)
        return self.out(self.drop(h))  # logits (B, L, vocab)


# ---------------------------------------------------------------- loop helpers
def _gather_preds(logits, items, corrects, splits, cand, phase_code):
    """Dịch next-step: dự đoán vị trí p (1..L-1) từ output p-1, gather tại item[p].
    Trả (logit_scored, target_scored) theo mask cand & split==phase_code."""
    pred_logits = logits[:, :-1, :]                       # output tại 0..L-2
    tgt_item = items[:, 1:].unsqueeze(-1)                 # item tại 1..L-1
    gathered = pred_logits.gather(2, tgt_item).squeeze(-1)  # (B, L-1)
    target = corrects[:, 1:].float()
    mask = cand[:, 1:] & (splits[:, 1:] == phase_code)
    return gathered[mask], target[mask]


def run_eval(model, loader, device, phase_code):
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for inp, items, corrects, splits, cand in loader:
            inp = inp.to(device); items = items.to(device)
            corrects = corrects.to(device); splits = splits.to(device); cand = cand.to(device)
            logits = model(inp)
            g, t = _gather_preds(logits, items, corrects, splits, cand, phase_code)
            if g.numel():
                ps.append(torch.sigmoid(g).cpu().numpy())
                ys.append(t.cpu().numpy())
    if not ys:
        return {"auc": float("nan"), "accuracy": float("nan"), "n": 0}
    from src.evaluate import evaluate  # import cục bộ: xem ghi chú ở đầu file

    return evaluate(np.concatenate(ys), np.concatenate(ps))  # AUC gộp toàn cục


# ---------------------------------------------------------------- train
def train(subset: bool, tag: str) -> dict:
    global VOCAB, PAD_INPUT
    cfg = config.CONFIG
    config.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
    VOCAB = len(item2idx)
    PAD_INPUT = 2 * VOCAB

    data = load_sequences(subset)
    ds = WindowDataset(data, cfg["max_seq_len"], cfg["stride"])
    g = torch.Generator(); g.manual_seed(config.SEED)
    train_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=True,
                              collate_fn=collate, generator=g)
    eval_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=False, collate_fn=collate)

    model = DKT(VOCAB, cfg["embedding_dim"], cfg["hidden_dim"],
                cfg["num_layers"], cfg["dropout"]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"])
    bce = nn.BCEWithLogitsLoss()

    best_dev = -1.0; best_state = None; best_epoch = -1; no_improve = 0
    t0 = time.time()
    print(f"[DKT/{tag}] users={len(data)} windows={len(ds)} vocab={VOCAB} device={device.type}")
    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        total_loss = 0.0; nb = 0
        for inp, items, corrects, splits, cand in train_loader:
            inp = inp.to(device); items = items.to(device)
            corrects = corrects.to(device); splits = splits.to(device); cand = cand.to(device)
            logits = model(inp)
            g_logit, target = _gather_preds(logits, items, corrects, splits, cand,
                                            config.SPLIT2CODE["train"])
            if g_logit.numel() == 0:
                continue
            loss = bce(g_logit, target)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip"])
            opt.step()
            total_loss += loss.item(); nb += 1

        tr = run_eval(model, eval_loader, device, config.SPLIT2CODE["train"])
        dv = run_eval(model, eval_loader, device, config.SPLIT2CODE["dev"])
        print(f"  epoch {epoch:2d} | loss {total_loss/max(nb,1):.4f} | "
              f"train-AUC {tr['auc']:.4f} | dev-AUC {dv['auc']:.4f} | "
              f"{time.time()-t0:.0f}s")

        if dv["auc"] > best_dev:
            best_dev = dv["auc"]; best_epoch = epoch; no_improve = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            no_improve += 1
            if no_improve >= cfg["patience"]:
                print(f"  early stop (patience {cfg['patience']}) @ epoch {epoch}")
                break

    # test với checkpoint tốt nhất theo dev-AUC
    if best_state is not None:
        model.load_state_dict(best_state)
    test = run_eval(model, eval_loader, device, config.SPLIT2CODE["test"])
    elapsed = round(time.time() - t0, 1)
    print(f"[DKT/{tag}] BEST dev-AUC {best_dev:.4f} @ep{best_epoch} | "
          f"TEST AUC {test['auc']:.4f} ACC {test['accuracy']:.4f} n={test['n']:,} | {elapsed}s")

    return {
        "auc": test["auc"], "accuracy": test["accuracy"], "n": test["n"],
        "best_dev_auc": best_dev, "best_epoch": best_epoch,
        "n_users": len(data), "n_windows": len(ds),
        "hidden_dim": cfg["hidden_dim"], "epochs_run": epoch,
        "time_s": elapsed,
    }, (best_state, model)


def save_results(key: str, metrics: dict, group: str = "dkt") -> None:
    """Ghi kết quả vào models/results.json dưới `group` (mỗi họ mô hình một nhóm)."""
    path = config.MODELS_DIR / "results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.setdefault(group, {})[key] = metrics
    path.write_text(json.dumps(allr, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Da luu", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    if args.full:
        metrics, (best_state, _) = train(subset=False, tag="full")
        if best_state is not None:
            torch.save({"state_dict": best_state, "config": config.CONFIG,
                        "metrics": metrics}, config.MODELS_DIR / "dkt_best.pt")
        save_results("full", metrics)
    else:
        metrics, _ = train(subset=True, tag="subset")
        save_results("subset", metrics)


if __name__ == "__main__":
    main()
