"""Giai đoạn 3.4/M4 — UC-68 phục vụ mô hình DKT đã train.

Nạp dkt_best.pt + item2idx.json, cung cấp:
    predict_mastery(history, targets) -> {token: P(correct)}
- history: list[(token:str, correct:int)] lịch sử trả lời của user theo thứ tự thời gian.
- targets: list[token] cần ước lượng mastery (P trả lời đúng ở lần kế).
- token lạ (không có trong vocab SLAM) -> UNK; caller (cold-start UC-69) quyết định
  dùng prior. history rỗng -> trả None cho mọi target (chưa đủ ngữ cảnh -> cold-start).

Đây là "predict(user_history) -> mastery" theo pipeline §5; backend gọi qua REST nội bộ.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from src.dkt import DKT  # noqa: E402


class DKTServer:
    def __init__(self, ckpt_path: Path | None = None):
        ckpt_path = ckpt_path or (config.MODELS_DIR / "dkt_best.pt")
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Chưa có checkpoint {ckpt_path} — train DKT trước (src/dkt.py --full)")

        self.item2idx: dict[str, int] = json.loads(
            (config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8")
        )
        self.vocab = len(self.item2idx)
        self.max_len = config.CONFIG["max_seq_len"]

        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        cfg = ckpt.get("config", config.CONFIG)
        self.model = DKT(self.vocab, cfg["embedding_dim"], cfg["hidden_dim"],
                         cfg["num_layers"], cfg["dropout"])
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    def token_idx(self, token: str) -> int:
        return self.item2idx.get(token, config.UNK_IDX)

    @torch.no_grad()
    def _hidden_probs(self, history_idx: list[int], history_correct: list[int]) -> np.ndarray | None:
        """Chạy DKT trên lịch sử -> vector P(correct) cho MỌI item ở bước kế.
        Trả None nếu lịch sử rỗng (chưa đủ ngữ cảnh)."""
        if not history_idx:
            return None
        idx = history_idx[-self.max_len:]
        cor = history_correct[-self.max_len:]
        inp = torch.tensor([[2 * i + c for i, c in zip(idx, cor)]], dtype=torch.long)
        logits = self.model(inp)          # (1, L, vocab)
        last = logits[0, -1, :]           # dự đoán cho bước kế
        return torch.sigmoid(last).numpy()

    def predict_mastery(
        self, history: list[tuple[str, int]], targets: list[str]
    ) -> dict[str, float | None]:
        """Mastery = P(correct) cho từng target, dựa trên lịch sử nhân quả của user."""
        hist_idx = [self.token_idx(t) for t, _ in history]
        hist_cor = [int(c) for _, c in history]
        probs = self._hidden_probs(hist_idx, hist_cor)
        if probs is None:
            return {t: None for t in targets}  # cold-start: để caller áp prior
        # target ngoài vocab SLAM -> None (không có mastery thật, để caller dùng prior).
        # UNK chỉ dùng để mã hóa LỊCH SỬ, không dùng làm dự đoán target.
        return {
            t: (float(probs[self.item2idx[t]]) if t in self.item2idx else None)
            for t in targets
        }


@lru_cache(maxsize=1)
def get_server() -> DKTServer:
    """Singleton — nạp model 1 lần."""
    return DKTServer()


# ------------------------------------------------------------------ self-test
def _self_test() -> None:
    """Chứng minh serve tái hiện ĐÚNG model: tính AUC test trên mẫu user bằng serve,
    phải xấp xỉ DKT full test-AUC (~0.808)."""
    import pickle
    from src.evaluate import evaluate

    srv = get_server()
    with open(config.PROCESSED_DIR / "sequences.pkl", "rb") as f:
        data = pickle.load(f)

    config.set_seed()
    users = sorted(data.keys())
    sample = users[:300]  # mẫu để chạy nhanh
    test_code = config.SPLIT2CODE["test"]

    y_true, y_prob = [], []
    for u in sample:
        seq = data[u]
        items = seq["items"].tolist()
        corr = seq["corrects"].tolist()
        splits = seq["splits"].tolist()
        # với mỗi vị trí test t: dự đoán P(correct) tại item[t] từ lịch sử [0..t-1]
        for t in range(1, len(items)):
            if splits[t] != test_code:
                continue
            probs = srv._hidden_probs(items[:t], corr[:t])
            if probs is None:
                continue
            y_true.append(corr[t])
            y_prob.append(float(probs[items[t]]))

    m = evaluate(np.array(y_true), np.array(y_prob))
    print(f"[serve self-test] {len(sample)} user | n_test={m['n']:,} | "
          f"AUC={m['auc']:.4f} ACC={m['accuracy']:.4f}")
    print("  (so với DKT full test-AUC 0.8088 — xấp xỉ = serve tái hiện đúng model)")

    # demo API token-based
    idx2token = {v: k for k, v in srv.item2idx.items()}
    demo_u = sample[0]
    seq = data[demo_u]
    tr_mask = seq["splits"] == config.SPLIT2CODE["train"]
    hist = [(idx2token[int(i)], int(c))
            for i, c in zip(seq["items"][tr_mask][:50], seq["corrects"][tr_mask][:50])]
    targets = [idx2token[int(i)] for i in seq["items"][:5]]
    print("\n[demo predict_mastery] history 50 câu train, mastery 5 từ đầu:")
    for tok, p in srv.predict_mastery(hist, targets).items():
        print(f"  {tok:15s} -> {p:.3f}")
    print("[demo history rỗng] ->", srv.predict_mastery([], targets[:2]))


if __name__ == "__main__":
    _self_test()
