"""Dự đoán từng lượt (train/dev/test) của các mô hình đã huấn luyện, lưu ra npz.

Mỗi lượt được chấm đúng một lần theo mặt nạ `cand` giống hệt lúc huấn luyện.
Lưu: user, vị trí, split, item, dạng bài, 5 đặc trưng lịch sử, nhãn, xác suất.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
import config
from src import dkt as _dkt
from src.dkt import WindowDataset, collate, load_sequences
from src.dkt_feat import (FeatureDKT, HistoryWindowDataset, collate_history,
                          build_feature_table, _batch_feats)
from src.sakt import SAKT

OUT = ML / "an" / "out"; OUT.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(2)
cfg = config.CONFIG
item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
V = len(item2idx); _dkt.VOCAB = V; _dkt.PAD_INPUT = 2 * V
data = load_sequences(False)


def collect(ds, fn, step, name, bs=64):
    loader = DataLoader(ds, batch_size=bs, shuffle=False, collate_fn=fn)
    rec = {k: [] for k in ("u", "pos", "p")}
    t0 = time.time(); k = 0
    with torch.no_grad():
        for batch in loader:
            idx = list(range(k, k + batch[0].shape[0])); k += len(idx)
            prob, mask = step(batch)               # (B,L) và (B,L) bool
            m = mask.numpy()
            b, l = np.nonzero(m)
            ui = np.array([ds.index[i][0] for i in idx])[b]
            st = np.array([ds.index[i][1] for i in idx])[b]
            rec["u"].append(ui); rec["pos"].append(st + l)
            rec["p"].append(prob.numpy()[m])
    r = {k2: np.concatenate(v) for k2, v in rec.items()}
    print(f"{name}: {len(r['p']):,} lượt, {time.time()-t0:.0f}s", flush=True)
    return r


def save(name, r):
    np.savez_compressed(OUT / f"pred_{name}.npz", **r)


def run_feat(ckpt, name):
    ck = torch.load(ML / "models" / ckpt, map_location="cpu", weights_only=False)
    table = build_feature_table(item2idx)
    model = FeatureDKT(ck["feature_dim"], cfg["embedding_dim"], cfg["hidden_dim"],
                       cfg["num_layers"], cfg["dropout"])
    model.load_state_dict(ck["state_dict"]); model.eval()
    use_h = ck["use_history"]
    if use_h:
        ds = HistoryWindowDataset(data, cfg["max_seq_len"], cfg["stride"]); fn = collate_history
    else:
        ds = WindowDataset(data, cfg["max_seq_len"], cfg["stride"]); fn = collate

    def step(batch):
        logit = model(_batch_feats(batch, table, "cpu", use_h), batch[2])
        mask = torch.zeros_like(batch[4]); mask[:, 1:] = batch[4][:, 1:]
        mask &= batch[3] >= 0
        return torch.sigmoid(logit), mask
    return collect(ds, fn, step, name)


def run_id(ckpt, name, sakt=False):
    ck = torch.load(ML / "models" / ckpt, map_location="cpu", weights_only=False)
    if sakt:
        model = SAKT(V, cfg["embedding_dim"], cfg["nhead"], cfg["dim_feedforward"],
                     cfg["dropout"], cfg["max_seq_len"])
    else:
        model = _dkt.DKT(V, cfg["embedding_dim"], cfg["hidden_dim"], cfg["num_layers"], cfg["dropout"])
    model.load_state_dict(ck["state_dict"]); model.eval()
    ds = WindowDataset(data, cfg["max_seq_len"], cfg["stride"])

    def step(batch):
        inp, items, corrects, splits, cand = batch
        logits = model(inp)
        g = logits[:, :-1, :].gather(2, items[:, 1:].unsqueeze(-1)).squeeze(-1)
        prob = torch.zeros(items.shape); prob[:, 1:] = torch.sigmoid(g)
        mask = torch.zeros_like(cand); mask[:, 1:] = cand[:, 1:]
        mask &= splits >= 0
        return prob, mask
    return collect(ds, collate, step, name)


if __name__ == "__main__":
    which = sys.argv[1:]
    if "base" in which:
        # bảng tham chiếu theo (u, pos): split, item, format, nhãn, lịch sử
        from src.history_features import sequence_history
        users = list(data.values())
        rows = {k: [] for k in ("u", "pos", "split", "item", "fmt", "y")}
        hist = []
        for ui, s in enumerate(users):
            n = len(s["items"])
            rows["u"].append(np.full(n, ui)); rows["pos"].append(np.arange(n))
            rows["split"].append(s["splits"]); rows["item"].append(s["items"])
            rows["fmt"].append(s["formats"]); rows["y"].append(s["corrects"])
            hist.append(sequence_history(s["items"], s["corrects"], None))
        base = {k: np.concatenate(v) for k, v in rows.items()}
        base["hist"] = np.concatenate(hist)
        np.savez_compressed(OUT / "base.npz", **base)
        print("base", len(base["y"]))
    if "feat" in which:
        save("dkt_feat", run_feat("dkt_feat_slam_original.pt", "dkt_feat"))
    if "static" in which:
        save("dkt_feat_static", run_feat("dkt_feat_static_best.pt", "dkt_feat_static"))
    if "dkt" in which:
        save("dkt", run_id("dkt_best.pt", "dkt"))
    if "sakt" in which:
        save("sakt", run_id("sakt_best.pt", "sakt", sakt=True))
