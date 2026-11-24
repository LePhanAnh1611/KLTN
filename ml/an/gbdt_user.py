"""Các mô hình cơ sở trên cùng tập lượt mà DKT chấm (vị trí >= 1 của mỗi chuỗi).

1. Tỉ lệ đúng của từ (ước lượng trên train, làm trơn Laplace).
2. Tỉ lệ đúng của người học (trên train).
3. Kết quả lần trước của cặp người học – từ (0,5 nếu chưa gặp).
4. IRT một tham số: hồi quy logistic trên one-hot người học + one-hot từ.
5. Hồi quy logistic trên đúng 37 đặc trưng của DKT dựa trên đặc trưng.
6. Cây tăng cường (HistGradientBoosting) trên cùng 37 đặc trưng.
Siêu tham số chọn theo AUC trên dev, giống cách DKT dừng sớm theo dev.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import scipy.sparse as sps
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ML = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ML))
import config
from src.dkt_feat import build_feature_table

OUT = ML / "an" / "out"
b = dict(np.load(OUT / "base.npz"))
keep = b["pos"] >= 1
for k in list(b): b[k] = b[k][keep]
sp, y, item, u = b["split"], b["y"].astype(np.int8), b["item"], b["u"]
tr, dv = sp == 0, sp == 1
item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
table = build_feature_table(item2idx).numpy()
fmt1h = np.eye(config.FORMAT_DIM, dtype=np.float32)[b["fmt"]]
# đặc trưng cấp người học, tính nhân quả trên toàn chuỗi gốc (kể cả vị trí 0)
B0 = np.load(OUT / "base.npz")
o = np.lexsort((B0["pos"], B0["u"]))
U0, Y0 = B0["u"][o], B0["y"][o].astype(np.float32)
starts = np.r_[0, np.nonzero(np.diff(U0))[0] + 1]; ends = np.r_[starts[1:], len(U0)]
feat_u = np.zeros((len(U0), 3), dtype=np.float32)
for s0, e0 in zip(starts, ends):
    yy = Y0[s0:e0]; n = e0 - s0
    cs = np.r_[0, np.cumsum(yy)[:-1]]; cnt = np.arange(n)
    feat_u[s0:e0, 0] = np.where(cnt > 0, cs / np.maximum(cnt, 1), 0.85)      # tỉ lệ đúng tích lũy
    c20 = np.r_[np.zeros(1), np.cumsum(yy)]
    lo = np.maximum(np.arange(n) - 20, 0)
    w = np.arange(n) - lo
    feat_u[s0:e0, 1] = np.where(w > 0, (c20[np.arange(n)] - c20[lo]) / np.maximum(w, 1), 0.85)  # 20 lượt gần nhất
    feat_u[s0:e0, 2] = np.log1p(cnt) / np.log1p(5000)                          # số lượt đã làm
inv = np.empty_like(o); inv[o] = np.arange(len(o))
feat_u = feat_u[inv][B0["pos"] >= 1]
X = np.hstack([table[item], b["hist"], fmt1h, feat_u]).astype(np.float32)
print("X", X.shape, flush=True)
preds = {}

preds = {}
# 6. Cây tăng cường trên 37 đặc trưng: số vòng chọn theo dev
t0 = time.time()
m2 = HistGradientBoostingClassifier(max_iter=900, learning_rate=0.1, max_leaf_nodes=63,
                                    early_stopping=False, random_state=42).fit(X[tr], y[tr])
for i, pdv in enumerate(m2.staged_predict_proba(X[dv])):
    if (i + 1) % 150 == 0: print("dev", i + 1, round(roc_auc_score(y[dv], pdv[:, 1]), 4), flush=True)
preds["gbdt_user"] = m2.predict_proba(X)[:, 1]
print("gbdt_user", time.time() - t0, flush=True)

for k, p in preds.items():
    np.savez_compressed(OUT / f"pred_{k}.npz", u=u, pos=b["pos"], p=p.astype(np.float32))
    print(k, "test AUC", round(roc_auc_score(y[sp == 2], p[sp == 2]), 4))
