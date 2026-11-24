"""Mức giảm AUC test của DKT dựa trên đặc trưng khi xáo trộn từng nhóm đặc trưng.

- tĩnh: hoán vị hàng của bảng đặc trưng giữa các từ (mỗi từ mang đặc trưng của từ khác);
- lịch sử: xáo trộn 5 cột lịch sử giữa các lượt trong cùng batch;
- dạng bài: xáo trộn dạng bài giữa các lượt trong cùng batch.
Xáo trộn áp dụng cho cả đầu vào LSTM lẫn đầu vào bộ chấm. Lặp 3 lần, lấy trung bình.
"""
import json, sys
from pathlib import Path
import numpy as np, torch
from torch.utils.data import DataLoader
from sklearn.metrics import roc_auc_score

ML = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ML))
import config
from src import dkt as _dkt
from src.dkt import load_sequences
from src.dkt_feat import FeatureDKT, HistoryWindowDataset, collate_history, build_feature_table, _batch_feats

torch.set_num_threads(1)
cfg = config.CONFIG
item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
V = len(item2idx); _dkt.VOCAB = V; _dkt.PAD_INPUT = 2 * V
table0 = build_feature_table(item2idx)
ck = torch.load(ML / "models/dkt_feat_slam_original.pt", map_location="cpu", weights_only=False)
model = FeatureDKT(ck["feature_dim"], cfg["embedding_dim"], cfg["hidden_dim"], cfg["num_layers"], cfg["dropout"])
model.load_state_dict(ck["state_dict"]); model.eval()
ds = HistoryWindowDataset(load_sequences(False), cfg["max_seq_len"], cfg["stride"])
from torch.utils.data import Subset
_idx = [i for i, (ui, a, e, sf) in enumerate(ds.index) if (ds.data[ui]["splits"][max(a, sf):e] == 2).any()]
loader = DataLoader(Subset(ds, _idx), batch_size=64, shuffle=False, collate_fn=collate_history)
print("cửa sổ test:", len(_idx), flush=True)


def run(mode, seed):
    g = torch.Generator().manual_seed(seed)
    table = table0
    if mode == "static":
        perm = torch.randperm(V - 2, generator=g) + 2
        table = table0.clone(); table[2:] = table0[perm]
    ys, ps = [], []
    with torch.no_grad():
        for batch in loader:
            batch = list(batch)
            valid = batch[3] >= 0
            if mode == "history":
                hist = batch[5]; flat = hist[valid]; flat = flat[torch.randperm(len(flat), generator=g)]
                hist = hist.clone(); hist[valid] = flat; batch[5] = hist
            if mode == "format":
                f = batch[7]; flat = f[valid]; flat = flat[torch.randperm(len(flat), generator=g)]
                f = f.clone(); f[valid] = flat; batch[7] = f
            logit = model(_batch_feats(batch, table, "cpu", True), batch[2])
            m = torch.zeros_like(batch[4]); m[:, 1:] = batch[4][:, 1:] & (batch[3][:, 1:] == 2)
            ps.append(torch.sigmoid(logit[m]).numpy()); ys.append(batch[2][m].numpy())
    return roc_auc_score(np.concatenate(ys), np.concatenate(ps))


base = run("none", 0); res = {"base": round(base, 4)}
for mode in ("static", "history", "format"):
    a = [run(mode, s) for s in (1, 2, 3)]
    res[mode] = {"auc": round(float(np.mean(a)), 4), "drop": round(float(base - np.mean(a)), 4)}
    print(mode, res[mode], flush=True)
json.dump(res, open(ML / "an/out/permute.json", "w"), indent=1)
print(res)
