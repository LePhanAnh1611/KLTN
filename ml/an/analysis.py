"""Tổng hợp mọi phân tích cho mục 4.3 từ các file pred_*.npz. Ghi an/out/analysis.json."""
import json, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score, log_loss

ML = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ML))
import config
from src.dkt_feat import build_feature_table

OUT = ML / "an" / "out"
b = dict(np.load(OUT / "base.npz"))
keep = b["pos"] >= 1
for k in list(b): b[k] = b[k][keep]
key = b["u"].astype(np.int64) * 100000 + b["pos"]
order = np.argsort(key); key = key[order]
for k in list(b): b[k] = b[k][order]
y = b["y"].astype(np.int8); sp = b["split"]

MODELS = ["item_rate", "user_rate", "last_result", "irt", "bkt", "logreg", "gbdt", "gbdt_user", "sakt", "dkt", "dkt_feat"]
P = {}
for m in MODELS:
    f = OUT / f"pred_{m}.npz"
    if not f.exists(): continue
    d = np.load(f); kk = d["u"].astype(np.int64) * 100000 + d["pos"]
    o = np.argsort(kk); kk = kk[o]; p = d["p"][o].astype(np.float64)
    idx = np.searchsorted(kk, key); ok = (idx < len(kk)) & (kk[np.minimum(idx, len(kk) - 1)] == key)
    full = np.full(len(key), np.nan); full[ok] = p[idx[ok]]
    P[m] = full
print("mô hình:", list(P), flush=True)


def ece(yy, pp, bins=10):
    e = np.linspace(0, 1, bins + 1); w = np.digitize(pp, e[1:-1]); tot = 0
    rows = []
    for i in range(bins):
        m = w == i
        if m.sum():
            tot += m.sum() / len(yy) * abs(yy[m].mean() - pp[m].mean())
            rows.append([round(float(pp[m].mean()), 4), round(float(yy[m].mean()), 4), int(m.sum())])
    return tot, rows


R = {"n": {s: int((sp == c).sum()) for s, c in (("train", 0), ("dev", 1), ("test", 2))},
     "pos_rate_test": round(float(y[sp == 2].mean()), 4), "overall": {}, "reliability": {}}
for m, p in P.items():
    r = {}
    for s, c in (("train", 0), ("dev", 1), ("test", 2)):
        msk = (sp == c) & ~np.isnan(p)
        r[f"auc_{s}"] = round(roc_auc_score(y[msk], p[msk]), 4)
    t = (sp == 2) & ~np.isnan(p); yt, pt = y[t], np.clip(p[t], 1e-6, 1 - 1e-6)
    e, rows = ece(yt, pt)
    r.update(acc=round(float(((pt >= .5) == yt).mean()), 4), brier=round(float(((pt - yt) ** 2).mean()), 4),
             logloss=round(log_loss(yt, pt), 4), ece=round(float(e), 4), mean_p=round(float(pt.mean()), 4))
    R["overall"][m] = r; R["reliability"][m] = rows
    print(m, r, flush=True)
R["brier_const"] = round(float(((y[sp == 2].mean() - y[sp == 2]) ** 2).mean()), 4)

# ---- bootstrap theo người học trên test
test = sp == 2; ut = b["u"][test]; yt = y[test]
users = np.unique(ut); grp = {uu: np.nonzero(ut == uu)[0] for uu in users} if False else None
o = np.argsort(ut, kind="stable"); us, st = np.unique(ut[o], return_index=True); en = np.r_[st[1:], len(o)]
rng = np.random.default_rng(42); B = 300
BM = [m for m in ["irt", "bkt", "logreg", "gbdt", "gbdt_user", "sakt", "dkt", "dkt_feat", "last_result", "item_rate"] if m in P]
boot = {m: [] for m in BM}
for i in range(B):
    pick = rng.integers(0, len(us), len(us))
    idx = np.concatenate([o[st[j]:en[j]] for j in pick])
    for m in BM:
        boot[m].append(roc_auc_score(yt[idx], P[m][test][idx]))
boot = {m: np.array(v) for m, v in boot.items()}
R["ci"] = {m: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] for m, v in boot.items()}
R["diff"] = {}
for a, c in [("dkt_feat", "dkt"), ("dkt_feat", "logreg"), ("dkt_feat", "gbdt"), ("dkt_feat", "gbdt_user"), ("dkt_feat", "sakt"), ("dkt_feat", "irt"), ("dkt", "sakt"), ("gbdt", "logreg")]:
    if a in boot and c in boot:
        d = boot[a] - boot[c]
        R["diff"][f"{a}-{c}"] = [round(float(np.mean(d)), 4), round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]
print("ci", R["ci"], "\ndiff", R["diff"], flush=True)

# ---- nhóm con trên test
item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
idx2item = {v: k for k, v in item2idx.items()}
table = build_feature_table(item2idx).numpy()
h = b["hist"]
seen = np.where(h[:, 3] == 1, 0, np.rint(np.exp(h[:, 0] * np.log(21.0)) - 1)).astype(int)
ntr = np.bincount(b["item"][sp == 0], minlength=len(item2idx))
cefr = np.where(table[:, 7] == 1, -1, np.argmax(table[:, :6], axis=1))
groups = {
    "format": (b["fmt"], {0: "reverse_tap", 1: "reverse_translate", 2: "listen"}),
    "seen": (np.digitize(seen, [1, 3, 10]), {0: "chưa gặp", 1: "1–2 lần", 2: "3–9 lần", 3: "từ 10 lần"}),
    "freq": (np.digitize(ntr[b["item"]], [100, 1000, 10000]), {0: "dưới 100", 1: "100–999", 2: "1.000–9.999", 3: "từ 10.000"}),
    "cefr": (cefr[b["item"]], {-1: "không rõ", 0: "A1", 1: "A2", 2: "B1", 3: "B2", 4: "C1", 5: "C2"}),
}
R["groups"] = {}
for gname, (gv, labels) in groups.items():
    rows = []
    for code, lab in labels.items():
        msk = test & (gv == code)
        if msk.sum() < 200 or y[msk].min() == y[msk].max(): continue
        row = {"group": lab, "n": int(msk.sum()), "pos_rate": round(float(y[msk].mean()), 3)}
        for m in ("dkt_feat", "dkt", "logreg", "gbdt", "gbdt_user"):
            if m in P: row[m] = round(roc_auc_score(y[msk], P[m][msk]), 4)
        e, _ = ece(y[msk], P["dkt_feat"][msk]); row["ece_feat"] = round(float(e), 4)
        rows.append(row)
    R["groups"][gname] = rows
    print(gname, rows, flush=True)

# ---- lỗi tự tin cao (dkt_feat, test)
pf = P["dkt_feat"]; t = test
hi_wrong = t & (pf >= 0.9) & (y == 0); lo_right = t & (pf < 0.5) & (y == 1)
R["errors"] = {"n_p_ge_0.9": int((t & (pf >= .9)).sum()), "wrong_among_p_ge_0.9": int(hi_wrong.sum()),
               "n_p_lt_0.5": int((t & (pf < .5)).sum()), "right_among_p_lt_0.5": int(lo_right.sum())}
for nm, msk in (("hi_wrong", hi_wrong),):
    R["errors"][nm + "_by_format"] = {lab: int((msk & (b["fmt"] == c)).sum()) for c, lab in groups["format"][1].items()}
    R["errors"][nm + "_by_seen"] = {lab: int((msk & (groups["seen"][0] == c)).sum()) for c, lab in groups["seen"][1].items()}
    cnt = np.bincount(b["item"][msk], minlength=len(item2idx))
    top = np.argsort(-cnt)[:15]
    R["errors"][nm + "_top_items"] = [[idx2item[i], int(cnt[i]), int(((b["item"] == i) & t).sum())] for i in top]
    fmt_all = {lab: int((t & (pf >= .9) & (b["fmt"] == c)).sum()) for c, lab in groups["format"][1].items()}
    R["errors"]["p_ge_0.9_by_format"] = fmt_all
print(R["errors"], flush=True)
json.dump(R, open(OUT / "analysis.json", "w"), ensure_ascii=False, indent=1)
