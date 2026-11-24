"""Thực nghiệm giữ lại từ: kiểm chứng DKT dựa trên đặc trưng chấm được từ CHƯA TỪNG HUẤN LUYỆN.

Chọn ngẫu nhiên 20% số từ (seed 42). Mọi lượt của các từ này ở phần train bị XÓA
khỏi chuỗi trước khi tính đặc trưng lịch sử, nên mô hình không nhận được bất kỳ
tín hiệu nào về chúng khi huấn luyện, kể cả làm ngữ cảnh. Dừng sớm theo AUC dev
chỉ trên các từ còn lại. Cuối cùng chấm test riêng cho từ bị giữ lại và từ đã thấy.
Cấu hình huấn luyện giữ nguyên như bản chính (dkt_feat.py).
"""
import json, sys, time
from pathlib import Path
import numpy as np
import torch, torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import roc_auc_score

ML = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ML))
import config
from src import dkt as _dkt
from src.dkt import load_sequences
from src.dkt_feat import (FeatureDKT, HistoryWindowDataset, collate_history,
                          build_feature_table, _batch_feats, _scored)
from src.features import FEATURE_DIM
from src.history_features import HISTORY_DIM

OUT = ML / "an" / "out"
torch.set_num_threads(2)
cfg = dict(config.CONFIG); cfg["epochs"] = int(sys.argv[1]) if len(sys.argv) > 1 else 60
config.set_seed()
item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
V = len(item2idx); _dkt.VOCAB = V; _dkt.PAD_INPUT = 2 * V
table = build_feature_table(item2idx)

rng = np.random.default_rng(42)
real = np.arange(2, V)
held = np.zeros(V, dtype=bool); held[rng.choice(real, int(0.2 * len(real)), replace=False)] = True
np.save(OUT / "held_items.npy", np.nonzero(held)[0])

data = load_sequences(False)
removed = 0
for k, s in data.items():
    drop = (s["splits"] == 0) & held[s["items"]]
    removed += int(drop.sum())
    for f in ("items", "corrects", "splits", "formats"):
        s[f] = s[f][~drop]
print("đã xóa", removed, "lượt train của", int(held.sum()), "từ", flush=True)

ds = HistoryWindowDataset(data, cfg["max_seq_len"], cfg["stride"])
g = torch.Generator(); g.manual_seed(config.SEED)
train_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=True, collate_fn=collate_history, generator=g)
from torch.utils.data import Subset
def _has(code):
    return [i for i, (ui, a, e, sf) in enumerate(ds.index) if (ds.data[ui]["splits"][max(a, sf):e] == code).any()]
dev_loader = DataLoader(Subset(ds, _has(1)), batch_size=cfg["batch_size"], shuffle=False, collate_fn=collate_history)
test_loader = DataLoader(Subset(ds, _has(2)), batch_size=cfg["batch_size"], shuffle=False, collate_fn=collate_history)
n_feat = FEATURE_DIM + HISTORY_DIM + config.FORMAT_DIM
model = FeatureDKT(n_feat, cfg["embedding_dim"], cfg["hidden_dim"], cfg["num_layers"], cfg["dropout"])
opt = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"]); bce = nn.BCEWithLogitsLoss()
held_t = torch.from_numpy(held)


def evaluate(code):
    model.eval(); ys, ps, hs = [], [], []
    with torch.no_grad():
        for batch in (dev_loader if code == 1 else test_loader):
            logit = model(_batch_feats(batch, table, "cpu", True), batch[2])
            mask = torch.zeros_like(batch[4]); mask[:, 1:] = batch[4][:, 1:] & (batch[3][:, 1:] == code)
            ps.append(torch.sigmoid(logit[mask]).numpy()); ys.append(batch[2][mask].numpy())
            hs.append(held_t[batch[1][mask]].numpy())
    return np.concatenate(ys), np.concatenate(ps), np.concatenate(hs)


best, best_ep, best_state, bad = -1, 0, None, 0
t0 = time.time()
for ep in range(1, cfg["epochs"] + 1):
    model.train()
    for batch in train_loader:
        logit = model(_batch_feats(batch, table, "cpu", True), batch[2])
        gl, tg = _scored(logit, batch[2], batch[3], batch[4], 0)
        fl, ft = _scored(logit, batch[2], batch[3], batch[4], 0, batch[6], True)
        gl = torch.cat([gl, fl]); tg = torch.cat([tg, ft])
        if gl.numel() == 0: continue
        loss = bce(gl, tg); opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip"]); opt.step()
    y, p, h = evaluate(1)
    a = roc_auc_score(y[~h], p[~h])
    yt_, pt_, ht_ = evaluate(2) if ep % 5 == 0 else (None, None, None)
    extra = "" if yt_ is None else f" | test thấy={roc_auc_score(yt_[~ht_], pt_[~ht_]):.4f} giữ lại={roc_auc_score(yt_[ht_], pt_[ht_]):.4f}"
    print(f"epoch {ep} dev-AUC(từ đã thấy)={a:.4f} {time.time()-t0:.0f}s{extra}", flush=True)
    if a > best:
        best, best_ep, bad = a, ep, 0
        best_state = {k: v.clone() for k, v in model.state_dict().items()}
        torch.save({"state_dict": best_state, "feature_dim": n_feat, "use_history": True, "best_epoch": ep},
                   OUT / "dkt_feat_wordholdout.pt")
    else:
        bad += 1
        if bad >= cfg["patience"]: break

model.load_state_dict(best_state)
y, p, h = evaluate(2)
res = {"best_epoch": best_ep, "dev_auc_seen": round(best, 4), "n_held_items": int(held.sum()),
       "train_rows_removed": removed,
       "test_auc_seen": round(roc_auc_score(y[~h], p[~h]), 4), "test_n_seen": int((~h).sum()),
       "test_auc_held": round(roc_auc_score(y[h], p[h]), 4), "test_n_held": int(h.sum()),
       "seconds": round(time.time() - t0)}
np.savez_compressed(OUT / "wordholdout_test.npz", y=y, p=p, h=h)
json.dump(res, open(OUT / "wordholdout.json", "w"), indent=1)
print(res)
