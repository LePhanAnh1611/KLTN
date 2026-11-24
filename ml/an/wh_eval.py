"""Chấm checkpoint tốt nhất (theo dev) của thực nghiệm giữ lại từ, kèm KTC bootstrap theo người học."""
import json, sys
from pathlib import Path
import numpy as np, torch
from torch.utils.data import DataLoader, Subset
from sklearn.metrics import roc_auc_score

ML = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ML))
import config
from src import dkt as _dkt
from src.dkt import load_sequences
from src.dkt_feat import FeatureDKT, HistoryWindowDataset, collate_history, build_feature_table, _batch_feats

OUT = ML / "an" / "out"; torch.set_num_threads(2); cfg = config.CONFIG
item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
V = len(item2idx); _dkt.VOCAB = V; _dkt.PAD_INPUT = 2 * V
table = build_feature_table(item2idx)
held = np.zeros(V, dtype=bool); held[np.load(OUT / "held_items.npy")] = True
data = load_sequences(False)
for s in data.values():
    drop = (s["splits"] == 0) & held[s["items"]]
    for f in ("items", "corrects", "splits", "formats"): s[f] = s[f][~drop]
ds = HistoryWindowDataset(data, cfg["max_seq_len"], cfg["stride"])
idx = [i for i, (ui, a, e, sf) in enumerate(ds.index) if (ds.data[ui]["splits"][max(a, sf):e] == 2).any()]
loader = DataLoader(Subset(ds, idx), batch_size=64, shuffle=False, collate_fn=collate_history)
ck = torch.load(OUT / "dkt_feat_wordholdout.pt", map_location="cpu", weights_only=False)
model = FeatureDKT(ck["feature_dim"], cfg["embedding_dim"], cfg["hidden_dim"], cfg["num_layers"], cfg["dropout"])
model.load_state_dict(ck["state_dict"]); model.eval()
Y, P, H, U, NS = [], [], [], [], []
with torch.no_grad():
    for k0, batch in zip(range(0, len(idx), 64), loader):
        logit = model(_batch_feats(batch, table, "cpu", True), batch[2])
        m = torch.zeros_like(batch[4]); m[:, 1:] = batch[4][:, 1:] & (batch[3][:, 1:] == 2)
        Y.append(batch[2][m].numpy()); P.append(torch.sigmoid(logit[m]).numpy())
        H.append(held[batch[1][m].numpy()]); NS.append(batch[5][m][:, 3].numpy())
        uids = np.array([ds.index[i][0] for i in idx[k0:k0 + batch[0].shape[0]]])
        U.append(np.repeat(uids[:, None], m.shape[1], 1)[m.numpy()])
y, p, h, u, ns = map(np.concatenate, (Y, P, H, U, NS))

# mô hình gốc trên đúng các lượt test của từ bị giữ lại (mô hình gốc đã thấy các từ này)
b = np.load(OUT / "base.npz"); po = np.load(OUT / "pred_dkt_feat.npz")
kb = b["u"].astype(np.int64) * 100000 + b["pos"]; kp = po["u"].astype(np.int64) * 100000 + po["pos"]
o = np.argsort(kb); j = o[np.searchsorted(kb[o], kp)]
it, sp, yy = b["item"][j], b["split"][j], b["y"][j]
t = sp == 2
orig_held = roc_auc_score(yy[t & held[it]], po["p"][t & held[it]])
orig_seen = roc_auc_score(yy[t & ~held[it]], po["p"][t & ~held[it]])

rng = np.random.default_rng(42); us = np.unique(u); grp = [np.nonzero(u == x)[0] for x in us]
bs = {"held": [], "seen": [], "diff": []}
for _ in range(200):
    pick = np.concatenate([grp[i] for i in rng.integers(0, len(us), len(us))])
    a1 = roc_auc_score(y[pick][h[pick]], p[pick][h[pick]]); a2 = roc_auc_score(y[pick][~h[pick]], p[pick][~h[pick]])
    bs["held"].append(a1); bs["seen"].append(a2); bs["diff"].append(a2 - a1)
ci = {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] for k, v in bs.items()}
first = (ns == 1)
res = {"best_epoch": ck.get("best_epoch"), "n_held_items": int(held.sum()),
       "test_auc_held": round(roc_auc_score(y[h], p[h]), 4), "n_held": int(h.sum()), "pos_rate_held": round(float(y[h].mean()), 3),
       "test_auc_seen": round(roc_auc_score(y[~h], p[~h]), 4), "n_seen": int((~h).sum()), "pos_rate_seen": round(float(y[~h].mean()), 3),
       "ci": ci,
       "held_first_encounter_auc": round(roc_auc_score(y[h & first], p[h & first]), 4), "n_held_first": int((h & first).sum()),
       "seen_first_encounter_auc": round(roc_auc_score(y[~h & first], p[~h & first]), 4),
       "orig_model_auc_held": round(orig_held, 4), "orig_model_auc_seen": round(orig_seen, 4),
       "ece_held": None}
e = np.linspace(0, 1, 11); w = np.digitize(p[h], e[1:-1]); tot = 0
for i in range(10):
    mm = w == i
    if mm.sum(): tot += mm.sum() / h.sum() * abs(y[h][mm].mean() - p[h][mm].mean())
res["ece_held"] = round(float(tot), 4)
json.dump(res, open(OUT / "wordholdout_eval.json", "w"), indent=1); print(res)
