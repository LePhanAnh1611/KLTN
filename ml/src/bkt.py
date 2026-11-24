"""Giai đoạn 3.3 — Baseline BKT (Bayesian Knowledge Tracing) trên SLAM en_es.

Chạy: (từ ml/)  python src/bkt.py            # subset debug rồi full
       python src/bkt.py --subset            # chỉ subset
       python src/bkt.py --full              # chỉ full

- 1 skill = 1 item (token). Mỗi skill ước lượng 4 tham số qua EM: p_init, p_learn,
  p_slip, p_guess.
- CHỐNG RÒ RỈ: tham số ước lượng CHỈ từ vị trí split=train.
- Đánh giá CHỈ trên split=test; mỗi vị trí test dự đoán P(correct) từ lịch sử TRƯỚC
  ĐÓ của user trên skill đó (cập nhật niềm tin nhân quả, không dùng tương lai).
- Metric qua evaluate.evaluate() (dùng chung với DKT/SAKT). Kết quả -> models/results.json.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from src.evaluate import evaluate  # noqa: E402

# giới hạn tham số để giữ mô hình định danh được (slip+guess < 1)
CLAMP = {"init": (0.01, 0.99), "learn": (0.01, 0.99), "slip": (0.01, 0.30), "guess": (0.01, 0.30)}
EM_MAX_ITER = 30
EM_TOL = 1e-4
MIN_OBS_PER_SKILL = 20      # skill ít hơn -> dùng tham số global
GLOBAL_FIT_SAMPLE = 20000   # số chuỗi lấy mẫu để fit tham số global
TEST_CODE = config.SPLIT2CODE["test"]
TRAIN_CODE = config.SPLIT2CODE["train"]


# ---------------------------------------------------------------- load data
def load_full() -> dict:
    with open(config.PROCESSED_DIR / "sequences.pkl", "rb") as f:
        return pickle.load(f)


def load_subset() -> dict:
    code = config.SPLIT2CODE
    data = {}
    with open(config.PROCESSED_DIR / "sequences_subset.jsonl", encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            triples = o["seq"]
            data[o["user"]] = {
                "items": np.array([t[0] for t in triples], dtype=np.int32),
                "corrects": np.array([t[1] for t in triples], dtype=np.int8),
                "splits": np.array([code[t[2]] for t in triples], dtype=np.int8),
            }
    return data


# ---------------------------------------------------------------- EM fit
def fit_bkt_em(seqs: list[np.ndarray], init=(0.4, 0.15, 0.1, 0.2),
               max_iter=EM_MAX_ITER, tol=EM_TOL) -> dict:
    """EM (forward-backward có scaling) cho 1 skill. seqs: list mảng 0/1 (train)."""
    n = len(seqs)
    lengths = [min(len(s), config.CONFIG["max_seq_len"]) for s in seqs]
    L = max(lengths)
    O = np.zeros((n, L)); M = np.zeros((n, L), dtype=bool)
    for i, s in enumerate(seqs):
        li = lengths[i]
        O[i, :li] = s[:li]; M[i, :li] = True

    pi, pl, ps, pg = init
    prev_ll = -np.inf
    for _ in range(max_iter):
        b0 = np.where(O == 1, pg, 1 - pg)     # P(o | unknown)
        b1 = np.where(O == 1, 1 - ps, ps)     # P(o | known)

        # forward (scaled): c[:,t] = tổng chuẩn hóa; alpha = alpha/c
        a0 = np.zeros((n, L)); a1 = np.zeros((n, L)); c = np.ones((n, L))
        z0 = (1 - pi) * b0[:, 0]; z1 = pi * b1[:, 0]
        s = z0 + z1; s = np.where(s <= 0, 1.0, s)
        c[:, 0] = s; a0[:, 0] = z0 / s; a1[:, 0] = z1 / s
        for t in range(1, L):
            v = M[:, t]
            z0 = a0[:, t - 1] * (1 - pl) * b0[:, t]
            z1 = (a0[:, t - 1] * pl + a1[:, t - 1]) * b1[:, t]
            s = z0 + z1; s = np.where(s <= 0, 1.0, s)
            a0[:, t] = np.where(v, z0 / s, a0[:, t - 1])
            a1[:, t] = np.where(v, z1 / s, a1[:, t - 1])
            c[:, t] = np.where(v, s, 1.0)

        # backward (scaled cùng c)
        be0 = np.ones((n, L)); be1 = np.ones((n, L))
        for t in range(L - 2, -1, -1):
            nv = M[:, t + 1]
            x0 = ((1 - pl) * b0[:, t + 1] * be0[:, t + 1] + pl * b1[:, t + 1] * be1[:, t + 1]) / c[:, t + 1]
            x1 = (b1[:, t + 1] * be1[:, t + 1]) / c[:, t + 1]
            be0[:, t] = np.where(nv, x0, 1.0)
            be1[:, t] = np.where(nv, x1, 1.0)

        # gamma (posterior trạng thái)
        g0 = a0 * be0; g1 = a1 * be1
        gs = g0 + g1; gs = np.where(gs <= 0, 1.0, gs)
        g0 = np.where(M, g0 / gs, 0.0); g1 = np.where(M, g1 / gs, 0.0)

        # xi(unknown->known) cho t=0..L-2 (khi t+1 hợp lệ)
        Mt = M[:, 1:L]
        xi01 = (a0[:, :L - 1] * pl * b1[:, 1:L] * be1[:, 1:L]) / c[:, 1:L]
        xi01 = np.where(Mt, xi01, 0.0)
        g0t = np.where(Mt, g0[:, :L - 1], 0.0)

        corr = (O == 1)
        incorr = (O == 0) & M
        sum_g0 = g0.sum(); sum_g1 = g1.sum(); den_learn = g0t.sum()

        new_pi = g1[:, 0].mean()
        new_pl = xi01.sum() / den_learn if den_learn > 0 else pl
        new_pg = (g0 * corr).sum() / sum_g0 if sum_g0 > 0 else pg
        new_ps = (g1 * incorr).sum() / sum_g1 if sum_g1 > 0 else ps

        pi = float(np.clip(new_pi, *CLAMP["init"]))
        pl = float(np.clip(new_pl, *CLAMP["learn"]))
        ps = float(np.clip(new_ps, *CLAMP["slip"]))
        pg = float(np.clip(new_pg, *CLAMP["guess"]))

        ll = float(np.where(M, np.log(c), 0.0).sum())
        if abs(ll - prev_ll) < tol:
            break
        prev_ll = ll

    return {"p_init": pi, "p_learn": pl, "p_slip": ps, "p_guess": pg}


# ---------------------------------------------------------------- build & fit
def build_train_skill_seqs(data: dict) -> dict[int, list[np.ndarray]]:
    """Nhóm câu trả lời TRAIN theo (skill) -> danh sách chuỗi/user (giữ thứ tự)."""
    skill_seqs: dict[int, list[np.ndarray]] = {}
    for seq in data.values():
        items, corr, splits = seq["items"], seq["corrects"], seq["splits"]
        train_mask = splits == TRAIN_CODE
        if not train_mask.any():
            continue
        per_user: dict[int, list[int]] = {}
        for it, c in zip(items[train_mask], corr[train_mask]):
            per_user.setdefault(int(it), []).append(int(c))
        for it, lst in per_user.items():
            skill_seqs.setdefault(it, []).append(np.array(lst, dtype=np.int8))
    return skill_seqs


def fit_all_skills(skill_seqs: dict[int, list[np.ndarray]]) -> tuple[dict, dict]:
    config.set_seed()
    # global fallback: fit trên mẫu chuỗi gộp từ mọi skill
    all_seqs = [s for seqs in skill_seqs.values() for s in seqs]
    rng = np.random.default_rng(config.SEED)
    if len(all_seqs) > GLOBAL_FIT_SAMPLE:
        idx = rng.choice(len(all_seqs), GLOBAL_FIT_SAMPLE, replace=False)
        sample = [all_seqs[i] for i in idx]
    else:
        sample = all_seqs
    global_params = fit_bkt_em(sample)

    params: dict[int, dict] = {}
    for skill, seqs in skill_seqs.items():
        n_obs = sum(len(s) for s in seqs)
        params[skill] = global_params if n_obs < MIN_OBS_PER_SKILL else fit_bkt_em(
            seqs, init=(global_params["p_init"], global_params["p_learn"],
                        global_params["p_slip"], global_params["p_guess"]))
    return params, global_params


# ---------------------------------------------------------------- predict test
def predict_test(data: dict, params: dict, global_params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Duyệt chuỗi thời gian mỗi user, cập nhật niềm tin nhân quả, chấm ở test."""
    y_true: list[int] = []
    y_prob: list[float] = []
    for seq in data.values():
        belief: dict[int, float] = {}
        for it, c, sp in zip(seq["items"], seq["corrects"], seq["splits"]):
            it = int(it)
            p = params.get(it, global_params)
            pi, pl, ps, pg = p["p_init"], p["p_learn"], p["p_slip"], p["p_guess"]
            prior = belief.get(it, pi)
            p_correct = prior * (1 - ps) + (1 - prior) * pg
            if sp == TEST_CODE:
                y_true.append(int(c)); y_prob.append(p_correct)
            # cập nhật Bayes theo quan sát rồi áp chuyển học
            if c == 1:
                num = prior * (1 - ps); den = num + (1 - prior) * pg
            else:
                num = prior * ps; den = num + (1 - prior) * (1 - pg)
            post = num / den if den > 0 else prior
            belief[it] = post + (1 - post) * pl
    return np.array(y_true), np.array(y_prob)


# ---------------------------------------------------------------- run
def run(data: dict, tag: str) -> dict:
    t0 = time.time()
    skill_seqs = build_train_skill_seqs(data)
    params, global_params = fit_all_skills(skill_seqs)
    y_true, y_prob = predict_test(data, params, global_params)
    metrics = evaluate(y_true, y_prob)
    metrics.update({
        "n_users": len(data),
        "n_skills_fit": len(skill_seqs),
        "n_test": int(len(y_true)),
        "fit_predict_time_s": round(time.time() - t0, 1),
        "global_params": {k: round(v, 4) for k, v in global_params.items()},
    })
    print(f"[BKT/{tag}] AUC={metrics['auc']:.4f}  ACC={metrics['accuracy']:.4f}  "
          f"n_test={metrics['n_test']:,}  users={metrics['n_users']}  "
          f"time={metrics['fit_predict_time_s']}s")
    return metrics


def save_results(results: dict) -> None:
    path = config.MODELS_DIR / "results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    all_res = {}
    if path.exists():
        all_res = json.loads(path.read_text(encoding="utf-8"))
    all_res["bkt"] = results
    path.write_text(json.dumps(all_res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Đã lưu", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    do_subset = args.subset or not args.full
    do_full = args.full or not args.subset

    results = {}
    if do_subset:
        results["subset"] = run(load_subset(), "subset")
    if do_full:
        results["full"] = run(load_full(), "full")
    save_results(results)


if __name__ == "__main__":
    main()
