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

# 1–3 baseline đơn giản
n_it = np.bincount(item[tr], minlength=len(item2idx)); k_it = np.bincount(item[tr], weights=y[tr], minlength=len(item2idx))
preds["item_rate"] = (k_it[item] + 1) / (n_it[item] + 2)
nu = u.max() + 1
n_u = np.bincount(u[tr], minlength=nu); k_u = np.bincount(u[tr], weights=y[tr], minlength=nu)
preds["user_rate"] = (k_u[u] + 1) / (n_u[u] + 2)
preds["last_result"] = b["hist"][:, 4].astype(float)
preds["hist_ratio"] = b["hist"][:, 1].astype(float)


def pick(name, fits):
    best = max(fits, key=lambda t: t[1]); print(name, [(c, round(a, 4)) for c, _, a in [(f[2], 0, f[1]) for f in fits]], "->", best[2], flush=True)
    return best[0]


# 4. IRT 1PL
t0 = time.time()
Xs = sps.hstack([sps.csr_matrix((np.ones(len(u)), (np.arange(len(u)), u)), shape=(len(u), nu)),
                 sps.csr_matrix((np.ones(len(u)), (np.arange(len(u)), item)), shape=(len(u), len(item2idx)))]).tocsr()
fits = []
for C in (0.1, 1.0):
    m = LogisticRegression(C=C, max_iter=300, solver="lbfgs").fit(Xs[tr], y[tr])
    fits.append((m, roc_auc_score(y[dv], m.predict_proba(Xs[dv])[:, 1]), C))
m = pick("irt", fits); preds["irt"] = m.predict_proba(Xs)[:, 1]
print("irt", time.time() - t0, flush=True)

# 5. Hồi quy logistic trên 37 đặc trưng
t0 = time.time(); fits = []
for C in (0.01, 0.1, 1.0, 10.0):
    m = LogisticRegression(C=C, max_iter=500, solver="lbfgs").fit(X[tr], y[tr])
    fits.append((m, roc_auc_score(y[dv], m.predict_proba(X[dv])[:, 1]), C))
m = pick("logreg", fits); preds["logreg"] = m.predict_proba(X)[:, 1]
coef = dict(zip([*(f"s{i}" for i in range(table.shape[1])), "seen_count", "correct_ratio", "recency", "never_seen", "prev_correct", "fmt_tap", "fmt_translate", "fmt_listen", "fmt_other"], m.coef_[0].round(3).tolist()))
json.dump({"C": m.C, "coef": coef}, open(OUT / "logreg_coef.json", "w"), indent=1)
print("logreg", time.time() - t0, flush=True)

# 6. Cây tăng cường trên 37 đặc trưng: số vòng chọn theo dev
t0 = time.time()
m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.1, max_leaf_nodes=63,
                                   early_stopping=False, random_state=42).fit(X[tr], y[tr])
best_i, best_a = 0, 0
for i, pdv in enumerate(m.staged_predict_proba(X[dv])):
    if (i + 1) % 20 == 0:
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
