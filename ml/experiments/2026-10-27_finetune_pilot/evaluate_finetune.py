"""Thí nghiệm fine-tune phần phán đoán (scorer) của FeatureDKT trên dữ liệu pilot.

Không đụng vào mô hình đang phục vụ: chỉ đọc checkpoint, ghi kết quả ra scratchpad.
"""
import copy, json, math, re, sys
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression

S = Path(sys.argv[1]); ML = Path(sys.argv[2])
sys.path.insert(0, str(ML))
import config  # noqa
from src.serve_feat import FeatureDKTServer  # noqa
torch.manual_seed(0); np.random.seed(0)

# ---------------- dữ liệu ----------------
df = pd.read_csv(S / "seq.csv", parse_dates=["answered_at"])
_SPLIT = re.compile(r"[,;/]"); _PAR = re.compile(r"\([^)]*\)"); EDGE = " \t:-–—>"
def label(m):
    m = m if isinstance(m, str) else ""
    t = _PAR.sub(" ", m)
    head = next((h for h in (p.strip(EDGE) for p in _SPLIT.split(t)) if h), "")
    head = " ".join(head.split()) or m.strip()
    f = head.split(" ", 1)[0] if head else ""
    if f[:1].isupper() and not f.isupper():
        head = head[:1].lower() + head[1:]
    return head
multi = df.meaning.map(lambda m: label(m) != " ".join((m if isinstance(m, str) else "").split()))
bug0, bug1 = pd.Timestamp("2026-10-26T11:00Z"), pd.Timestamp("2026-10-27T02:30Z")
# Loại CẢ cửa sổ lỗi (mọi lượt trắc nghiệm/ghép cặp, đúng lẫn sai): lỗi lan sang cả
# từ một nghĩa nên không lọc theo từng lượt được; bỏ cả lượt đúng để không lệch nhãn.
bug = df.fmt.isin(["quiz", "matching"]) & df.answered_at.between(bug0, bug1)
df = df[~bug].reset_index(drop=True)
df["self"] = (df.fmt == df["mode"]) | df.fmt.isin(["flashcard", "sm2"])
start = pd.Timestamp("2026-10-15T17:00Z")
df["eval"] = (~df.self) & (df.answered_at >= start) & df.p.notna()
print(f"lượt (sau khi bỏ {int(bug.sum())} lượt lỗi chấm): {len(df)} | lượt dùng làm nhãn: {int(df["eval"].sum())}")

# ---------------- tái tạo đầu vào đúng như lúc phục vụ ----------------
srv = FeatureDKTServer(ML / "models" / "dkt_feat_best.pt")
model = srv.model
H, X, idx = [], [], []
with torch.no_grad():
    for uid, g in df.groupby("user_id", sort=False):
        g = g.reset_index()
        words = g.word.astype(str).tolist(); ys = g.y.astype(int).tolist()
        fmts = g.fmt.fillna("").tolist()
        pos_all = {w: p for w, p in zip(words, g.pos) if isinstance(p, str) and p}
        for t in range(len(g)):
            if not g.loc[t, "eval"]:
                continue
            ht, hy, hf = words[:t], ys[:t], fmts[:t]
            pos = {w: pos_all[w] for w in set(ht + [words[t]]) if w in pos_all}
            rows, stats = srv._history_rows(ht, hy, hf, pos)
            win = rows[-(srv.max_len - 1):] if len(rows) else rows
            if len(win):
                c = torch.tensor([hy[-len(win):]], dtype=torch.float32).unsqueeze(-1)
                f = torch.from_numpy(win[None])
                h, _ = model.lstm(model.in_proj(torch.cat([f * (1 - c), f * c], -1)))
                state = h[0, -1]
            else:
                state = torch.zeros(model.lstm.hidden_size)
            H.append(state.numpy().copy())
            X.append(srv._target_row(words[t], pos, fmts[t], stats, len(ht)))
            idx.append(g.loc[t, "index"])
H = np.stack(H).astype(np.float32); X = np.stack(X).astype(np.float32)
E = df.loc[idx].reset_index(drop=True)
with torch.no_grad():
    E["p_dkt"] = torch.sigmoid(model.scorer(torch.cat([torch.from_numpy(H), torch.from_numpy(X)], -1)).squeeze(-1)).numpy()
print(f"kiểm tra tái tạo: tương quan với p đã lưu = {np.corrcoef(E.p, E.p_dkt)[0,1]:.3f}, "
      f"lệch TB tuyệt đối = {np.abs(E.p - E.p_dkt).mean():.3f}")

# ---------------- chia theo thời gian 65 / 15 / 20 ----------------
order = E.answered_at.rank(method="first").to_numpy() / len(E)
split = np.where(order <= .65, "train", np.where(order <= .80, "val", "test"))
E["split"] = split
for s in ["train", "val", "test"]:
    m = E.split == s
    print(f"  {s:5s}: n={m.sum():4d} sai={(E.y[m]==0).sum():3d} "
          f"từ {E.answered_at[m].min():%d/%m %H:%M} đến {E.answered_at[m].max():%d/%m %H:%M}")
tr, va, te = [(E.split == s).to_numpy() for s in ["train", "val", "test"]]

# ---------------- baseline (chỉ dùng dữ liệu trước thời điểm dự đoán) ----------------
full = df.sort_values(["answered_at", "id"]).copy()
prior = full[full.answered_at < E.answered_at[tr].max()].y.mean()
def running(keys, a=1):
    c = full.groupby(keys).y.cumsum() - full.y; n = full.groupby(keys).cumcount()
    return (c + a * prior) / (n + a)
full["b_user"] = running("user_id"); full["b_item"] = running("item_id"); full["b_ui"] = running(["user_id", "item_id"])
E = E.merge(full[["id", "b_user", "b_item", "b_ui"]], on="id", how="left")

# ---------------- hồi quy logistic trên CÙNG đặc trưng, không có LSTM ----------------
lr = LogisticRegression(C=1.0, max_iter=2000).fit(X[tr], E.y[tr])
E["p_lr"] = lr.predict_proba(X)[:, 1]

# ---------------- fine-tune scorer (đóng băng LSTM), L2-SP ----------------
Ht, Xt = torch.from_numpy(H), torch.from_numpy(X); Y = torch.tensor(E.y.to_numpy(), dtype=torch.float32)
base = copy.deepcopy(model.scorer)
def fit(lam, lr_=1e-3, epochs=200, patience=20):
    sc = copy.deepcopy(base); sc.train()
    ref = [p.detach().clone() for p in base.parameters()]
    opt = torch.optim.Adam(sc.parameters(), lr=lr_)
    pos_w = None
    best, best_state, bad, hist = -1, None, 0, []
    itr = torch.from_numpy(np.where(tr)[0])
    for ep in range(epochs):
        perm = itr[torch.randperm(len(itr))]
        for b in perm.split(64):
            logit = sc(torch.cat([Ht[b], Xt[b]], -1)).squeeze(-1)
            loss = nn.functional.binary_cross_entropy_with_logits(logit, Y[b])
            loss = loss + lam * sum(((p - r) ** 2).sum() for p, r in zip(sc.parameters(), ref))
            opt.zero_grad(); loss.backward(); opt.step()
        sc.eval()
        with torch.no_grad():
            pv = torch.sigmoid(sc(torch.cat([Ht[va], Xt[va]], -1)).squeeze(-1)).numpy()
        sc.train()
        a = roc_auc_score(E.y[va], pv); hist.append(a)
        if a > best + 1e-4: best, best_state, bad = a, copy.deepcopy(sc.state_dict()), 0
        else:
            bad += 1
            if bad >= patience: break
    sc.load_state_dict(best_state); sc.eval()
    return sc, best, len(hist)
results = []
for lam in [0.0, 1e-3, 1e-2, 1e-1, 1.0]:
    sc, v, ep = fit(lam)
    results.append((v, lam, ep, sc))
    print(f"  λ(L2-SP)={lam:<6} val-AUC={v:.3f} (dừng ở epoch {ep})")
v, lam, ep, sc = max(results, key=lambda r: r[0])
print(f"→ chọn λ={lam} theo val-AUC (KHÔNG nhìn test)")
with torch.no_grad():
    E["p_ft"] = torch.sigmoid(sc(torch.cat([Ht, Xt], -1)).squeeze(-1)).numpy()

# ---------------- calibration (Platt) học trên val ----------------
def platt(col):
    z = np.log(np.clip(E[col], 1e-6, 1 - 1e-6) / np.clip(1 - E[col], 1e-6, 1))
    m = LogisticRegression(C=1e6).fit(z[va].to_numpy().reshape(-1, 1), E.y[va])
    return m.predict_proba(z.to_numpy().reshape(-1, 1))[:, 1]
E["p_dkt_cal"] = platt("p_dkt"); E["p_ft_cal"] = platt("p_ft")

# ---------------- đánh giá MỘT LẦN trên test ----------------
T = E[te]
def ece(y, p, k=10):
    b = np.minimum((p * k).astype(int), k - 1); tot = 0
    for i in range(k):
        m = b == i
        if m.any(): tot += m.sum() * abs(p[m].mean() - y[m].mean())
    return tot / len(y)
users = T.user_id.unique(); rng = np.random.default_rng(0); groups = {u: np.where(T.user_id == u)[0] for u in users}
boot_idx = [np.concatenate([groups[u] for u in rng.choice(users, len(users))]) for _ in range(2000)]
def ci(col, ref=None):
    vals = []
    for ix in boot_idx:
        y = T.y.to_numpy()[ix]
        if len(set(y)) < 2: continue
        a = roc_auc_score(y, T[col].to_numpy()[ix])
        vals.append(a - (roc_auc_score(y, T[ref].to_numpy()[ix]) if ref else 0))
    return np.percentile(vals, [2.5, 97.5])
print(f"\n== TẬP TEST (n={len(T)}, sai={(T.y==0).sum()}, {len(users)} người) ==")
rows = [("DKT gốc (đang chạy pilot)", "p_dkt"), ("DKT gốc + calibration", "p_dkt_cal"),
        ("DKT fine-tune scorer", "p_ft"), ("DKT fine-tune + calibration", "p_ft_cal"),
        ("Hồi quy logistic, cùng đặc trưng, không LSTM", "p_lr"),
        ("Baseline: theo người", "b_user"), ("Baseline: theo từ", "b_item"), ("Baseline: lần trước của từ", "b_ui")]
out = []
for name, c in rows:
    a = roc_auc_score(T.y, T[c]); lo, hi = ci(c)
    e = ece(T.y.to_numpy(), T[c].to_numpy())
    print(f"  {name:46s} AUC={a:.3f} [{lo:.3f}, {hi:.3f}]  ECE={e:.3f}")
    out.append(dict(model=name, auc=round(a, 4), ci=[round(lo, 4), round(hi, 4)], ece=round(e, 4)))
for c, ref, name in [("p_ft", "p_dkt", "fine-tune − gốc"), ("p_ft", "b_user", "fine-tune − baseline theo người"),
                     ("p_ft", "p_lr", "fine-tune − hồi quy logistic")]:
    lo, hi = ci(c, ref); d = roc_auc_score(T.y, T[c]) - roc_auc_score(T.y, T[ref])
    print(f"  Chênh AUC {name:34s} {d:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    out.append(dict(diff=name, value=round(d, 4), ci=[round(lo, 4), round(hi, 4)]))

# cơ chế: mô hình mới có dùng lịch sử của chính từ đó không?
g = full.groupby(["user_id", "item_id"]); full["prev_y"] = g.y.shift()
E = E.merge(full[["id", "prev_y"]], on="id", how="left")
k = E[E.prev_y.notna()]
print("\nLượt gặp lại, theo kết quả lần trước:")
print(k.groupby("prev_y")[["y", "p_dkt", "p_ft"]].mean().round(3).rename(
    columns={"y": "đúng thật", "p_dkt": "DKT gốc", "p_ft": "DKT fine-tune"}).to_string())
json.dump(dict(split_sizes={s: int((E.split == s).sum()) for s in ["train", "val", "test"]},
               lambda_l2sp=lam, results=out), open(S / "ft_results.json", "w"), ensure_ascii=False, indent=2)
torch.save({"scorer_state_dict": sc.state_dict(), "lambda": lam}, S / "dkt_feat_scorer_finetuned_pilot.pt")

# ================= ĐÁNH GIÁ CHÉO THEO NGƯỜI (leave-one-user-out) =================
# Mỗi lượt: giữ riêng 1 người, fine-tune scorer trên MỌI người còn lại, chấm người đó.
# Siêu tham số CỐ ĐỊNH từ trước (không dò trên dữ liệu đánh giá).
print("\n================ ĐÁNH GIÁ CHÉO THEO NGƯỜI ================")
LAM, EPOCHS, LR_ = 0.1, 30, 1e-3
uids = E.user_id.to_numpy()
E["cv_ft"] = np.nan; E["cv_ftcal"] = np.nan; E["cv_lr"] = np.nan; E["cv_dktcal"] = np.nan
def train_head(mask):
    sc_ = copy.deepcopy(base); sc_.train(); ref = [p.detach().clone() for p in base.parameters()]
    opt = torch.optim.Adam(sc_.parameters(), lr=LR_); ix = torch.from_numpy(np.where(mask)[0])
    for _ in range(EPOCHS):
        for b in ix[torch.randperm(len(ix))].split(64):
            logit = sc_(torch.cat([Ht[b], Xt[b]], -1)).squeeze(-1)
            loss = nn.functional.binary_cross_entropy_with_logits(logit, Y[b]) + \
                LAM * sum(((p - r) ** 2).sum() for p, r in zip(sc_.parameters(), ref))
            opt.zero_grad(); loss.backward(); opt.step()
    sc_.eval(); return sc_
def logit_(p): p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))
for u in np.unique(uids):
    te_m = uids == u; tr_m = ~te_m
    if E.y[tr_m].nunique() < 2: continue
    s_ = train_head(tr_m)
    with torch.no_grad():
        pf = torch.sigmoid(s_(torch.cat([Ht, Xt], -1)).squeeze(-1)).numpy()
    E.loc[te_m, "cv_ft"] = pf[te_m]
    for col, src_p in [("cv_ftcal", pf), ("cv_dktcal", E.p_dkt.to_numpy())]:
        m = LogisticRegression(C=1e6).fit(logit_(src_p[tr_m]).reshape(-1, 1), E.y[tr_m])
        E.loc[te_m, col] = m.predict_proba(logit_(src_p[te_m]).reshape(-1, 1))[:, 1]
    lr_m = LogisticRegression(C=1.0, max_iter=2000).fit(X[tr_m], E.y[tr_m])
    E.loc[te_m, "cv_lr"] = lr_m.predict_proba(X[te_m])[:, 1]
C = E.dropna(subset=["cv_ft"]).reset_index(drop=True)
us = C.user_id.unique(); grp = {u: np.where(C.user_id == u)[0] for u in us}
bix = [np.concatenate([grp[u] for u in rng.choice(us, len(us))]) for _ in range(2000)]
def ci2(col, ref=None):
    v = []
    for ix in bix:
        y = C.y.to_numpy()[ix]
        if len(set(y)) < 2: continue
        a = roc_auc_score(y, C[col].to_numpy()[ix]); v.append(a - (roc_auc_score(y, C[ref].to_numpy()[ix]) if ref else 0))
    return np.percentile(v, [2.5, 97.5])
print(f"n={len(C)}, sai={(C.y==0).sum()}, {len(us)} người")
cv_out = []
for name, c in [("DKT gốc", "p_dkt"), ("DKT gốc + calibration", "cv_dktcal"), ("DKT fine-tune scorer", "cv_ft"),
                ("DKT fine-tune + calibration", "cv_ftcal"), ("Hồi quy logistic, không LSTM", "cv_lr"),
                ("Baseline: theo người", "b_user"), ("Baseline: theo từ", "b_item"), ("Baseline: lần trước của từ", "b_ui")]:
    a = roc_auc_score(C.y, C[c]); lo, hi = ci2(c); e = ece(C.y.to_numpy(), C[c].to_numpy())
    print(f"  {name:34s} AUC={a:.3f} [{lo:.3f}, {hi:.3f}]  ECE={e:.3f}")
    cv_out.append(dict(model=name, auc=round(a, 4), ci=[round(lo, 4), round(hi, 4)], ece=round(e, 4)))
for c, ref, name in [("cv_ft", "p_dkt", "fine-tune − DKT gốc"), ("cv_ft", "b_user", "fine-tune − theo người"),
                     ("cv_ft", "b_item", "fine-tune − theo từ"), ("cv_ft", "cv_lr", "fine-tune − hồi quy logistic")]:
    lo, hi = ci2(c, ref); d = roc_auc_score(C.y, C[c]) - roc_auc_score(C.y, C[ref])
    print(f"  Chênh {name:30s} {d:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    cv_out.append(dict(diff=name, value=round(d, 4), ci=[round(lo, 4), round(hi, 4)]))
k = C[C.prev_y.notna()]
print(k.groupby("prev_y")[["y", "p_dkt", "cv_ft"]].mean().round(3).rename(
    columns={"y": "đúng thật", "p_dkt": "DKT gốc", "cv_ft": "fine-tune"}).to_string())
print("Calibration (fine-tune + calibration):")
b = np.minimum((C.cv_ftcal * 10).astype(int), 9)
print(C.groupby(b).agg(n=("y", "size"), p=("cv_ftcal", "mean"), dung=("y", "mean")).round(3).T.to_string())
json.dump(dict(time_split=out, user_cv=cv_out, n_cv=len(C), users_cv=int(len(us))),
          open(S / "ft_results.json", "w"), ensure_ascii=False, indent=2)
