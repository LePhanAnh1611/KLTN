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
X = np.hstack([table[item], b["hist"], fmt1h]).astype(np.float32)
print("X", X.shape, flush=True)
preds = {}

preds = {}
# 6. Cây tăng cường trên 37 đặc trưng: số vòng chọn theo dev
t0 = time.time()
m = HistGradientBoostingClassifier(max_iter=1500, learning_rate=0.1, max_leaf_nodes=63,
                                   early_stopping=False, random_state=42).fit(X[tr], y[tr])
best_i, best_a = 0, 0
for i, pdv in enumerate(m.staged_predict_proba(X[dv])):
    if (i + 1) % 50 == 0:
        a = roc_auc_score(y[dv], pdv[:, 1])
        if a > best_a: best_i, best_a = i + 1, a
print("gbdt best iter", best_i, round(best_a, 4), flush=True)
m2 = HistGradientBoostingClassifier(max_iter=best_i, learning_rate=0.1, max_leaf_nodes=63,
                                    early_stopping=False, random_state=42).fit(X[tr], y[tr])
preds["gbdt"] = m2.predict_proba(X)[:, 1]
print("gbdt", time.time() - t0, flush=True)

for k, p in preds.items():
    np.savez_compressed(OUT / f"pred_{k}.npz", u=u, pos=b["pos"], p=p.astype(np.float32))
    print(k, "test AUC", round(roc_auc_score(y[sp == 2], p[sp == 2]), 4))
