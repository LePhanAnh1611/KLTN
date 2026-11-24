"""Huấn luyện scorer CUỐI trên toàn bộ dữ liệu pilot sạch + gộp calibration Platt vào lớp cuối.
Siêu tham số cố định = cấu hình đã kiểm bằng đánh giá chéo theo người (λ=0.1, 30 epoch, lr=1e-3)."""
import copy, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
S = Path(sys.argv[1]); ML = Path(sys.argv[2]); sys.path.insert(0, str(ML))
from src.serve_feat import FeatureDKTServer  # noqa
torch.manual_seed(0); np.random.seed(0)
LAM, EPOCHS, LR_ = 0.1, 30, 1e-3

df = pd.read_csv(S / "seq.csv", parse_dates=["answered_at"])
df["self"] = (df.fmt == df["mode"]) | df.fmt.isin(["flashcard", "sm2"])
df["eval"] = (~df.self) & (df.answered_at >= pd.Timestamp("2026-10-15T17:00Z"))
srv = FeatureDKTServer(ML / "models" / "dkt_feat_best.pt"); model = srv.model
H, X, idx = [], [], []
with torch.no_grad():
    for uid, g in df.groupby("user_id", sort=False):
        g = g.reset_index(); words = g.word.astype(str).tolist(); ys = g.y.astype(int).tolist(); fmts = g.fmt.fillna("").tolist()
        pos_all = {w: p for w, p in zip(words, g.pos) if isinstance(p, str) and p}
        for t in range(len(g)):
            if not g.loc[t, "eval"]: continue
            ht, hy, hf = words[:t], ys[:t], fmts[:t]
            pos = {w: pos_all[w] for w in set(ht + [words[t]]) if w in pos_all}
            rows, stats = srv._history_rows(ht, hy, hf, pos)
            win = rows[-(srv.max_len - 1):] if len(rows) else rows
            if len(win):
                c = torch.tensor([hy[-len(win):]], dtype=torch.float32).unsqueeze(-1); f = torch.from_numpy(win[None])
                h, _ = model.lstm(model.in_proj(torch.cat([f * (1 - c), f * c], -1))); state = h[0, -1]
            else:
                state = torch.zeros(model.lstm.hidden_size)
            H.append(state.numpy().copy()); X.append(srv._target_row(words[t], pos, fmts[t], stats, len(ht))); idx.append(g.loc[t, "index"])
E_ = df.loc[idx].reset_index(drop=True)
Ht, Xt = torch.from_numpy(np.stack(H)), torch.from_numpy(np.stack(X).astype(np.float32))
Y = torch.tensor(E_.y.to_numpy(), dtype=torch.float32); uids = E_.user_id.to_numpy()
print(f"nhãn: {len(E_)} lượt, {int((E_.y==0).sum())} sai, {len(np.unique(uids))} người")
base = copy.deepcopy(model.scorer)
def train_head(mask, seed=0):
    torch.manual_seed(seed)
    sc = copy.deepcopy(base); sc.train(); ref = [p.detach().clone() for p in base.parameters()]
    opt = torch.optim.Adam(sc.parameters(), lr=LR_); ix = torch.from_numpy(np.where(mask)[0])
    for _ in range(EPOCHS):
        for b in ix[torch.randperm(len(ix))].split(64):
            logit = sc(torch.cat([Ht[b], Xt[b]], -1)).squeeze(-1)
            loss = nn.functional.binary_cross_entropy_with_logits(logit, Y[b]) + LAM * sum(((p - r) ** 2).sum() for p, r in zip(sc.parameters(), ref))
            opt.zero_grad(); loss.backward(); opt.step()
    sc.eval(); return sc
def logits(sc):
    with torch.no_grad(): return sc(torch.cat([Ht, Xt], -1)).squeeze(-1).numpy()
# 1) Đánh giá chéo theo người -> logit "chưa thấy" của mọi lượt, dùng để học Platt (không rò rỉ)
cv = np.zeros(len(E_))
for u in np.unique(uids):
    m = uids == u; cv[m] = logits(train_head(~m))[m]
with torch.no_grad(): base_logit = logits(base)
platt = LogisticRegression(C=1e6).fit(cv.reshape(-1, 1), E_.y)
a, b = float(platt.coef_[0, 0]), float(platt.intercept_[0])
def ece(y, p, k=10):
    bb = np.minimum((p * k).astype(int), k - 1); return sum((bb == i).sum() * abs(p[bb == i].mean() - y[bb == i].mean()) for i in range(k) if (bb == i).any()) / len(y)
sig = lambda z: 1 / (1 + np.exp(-z)); y = E_.y.to_numpy()
print(f"CV  DKT gốc     AUC={roc_auc_score(y, base_logit):.3f} ECE={ece(y, sig(base_logit)):.3f}")
print(f"CV  fine-tune   AUC={roc_auc_score(y, cv):.3f} ECE={ece(y, sig(cv)):.3f}")
print(f"Platt a={a:.3f} b={b:.3f}  (ECE sau Platt, học trên chính CV nên lạc quan: {ece(y, sig(a*cv+b)):.3f})")
# 2) Scorer cuối: huấn luyện trên TẤT CẢ, rồi gộp Platt vào Linear cuối: logit' = a*logit + b
final = train_head(np.ones(len(E_), bool))
last = final[-1]
with torch.no_grad():
    last.weight.mul_(a); last.bias.mul_(a).add_(b)
# 3) Checkpoint mới = checkpoint gốc, chỉ thay trọng số scorer
ckpt = torch.load(ML / "models" / "dkt_feat_best.pt", map_location="cpu", weights_only=False)
sd = ckpt["state_dict"]; new = final.state_dict(); n = 0
for k, v in new.items():
    sd["scorer." + k] = v.clone(); n += 1
ckpt["fine_tune"] = dict(
    date=datetime.now(timezone.utc).isoformat(), data="pilot dump 2026-10-27 21:34 (sau sửa lỗi chấm 26/10)",
    n_labels=int(len(E_)), n_wrong=int((y == 0).sum()), n_users=int(len(np.unique(uids))),
    method="đóng băng LSTM/in_proj, huấn luyện lại scorer, L2-SP λ=0.1, 30 epoch, lr=1e-3; Platt (học trên dự đoán đánh giá chéo theo người) gộp vào Linear cuối",
    platt=dict(a=a, b=b), cv_auc_base=round(roc_auc_score(y, base_logit), 4), cv_auc_finetune=round(roc_auc_score(y, cv), 4),
    base_checkpoint="dkt_feat_slam_original.pt")
torch.save(ckpt, S / "dkt_feat_pilot_ft.pt")
print(f"đã thay {n} tensor scorer -> {S/'dkt_feat_pilot_ft.pt'}")
json.dump(ckpt["fine_tune"], open(S / "fine_tune_meta.json", "w"), ensure_ascii=False, indent=2)
