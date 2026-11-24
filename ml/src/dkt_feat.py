"""DKT **feature-based** — biến thể mà mục 2.2 `docs/system-spec.md` yêu cầu.

Chạy: (từ ml/)
    python src/dkt_feat.py --subset      # debug nhanh, in AUC mỗi epoch
    python src/dkt_feat.py --full        # train full, early stopping theo dev-AUC

Khác DKT gốc (`src/dkt.py`) ở đúng hai chỗ, và đó là toàn bộ vấn đề:

|                | DKT gốc (ID)                        | Bản này (đặc trưng)                    |
|----------------|-------------------------------------|----------------------------------------|
| Đầu vào bước t | `Embedding[2*item + correct]`        | `[f(item)·(1−c) ; f(item)·c]`          |
| Đầu ra         | `Linear(hidden, vocab)` rồi gather   | `scorer([h ; f(item kế tiếp)])` → 1 số |

Bỏ được lớp `Linear(hidden, vocab)` mới là mấu chốt: **mô hình không còn chiều
nào gắn với một từ cụ thể**, nên không còn khái niệm "từ ngoài vocab". Muốn chấm
một từ chưa từng thấy, chỉ cần tính được `f(...)` của nó.

Lưu ý cách đọc code: lúc huấn luyện ta vẫn tra đặc trưng qua *bảng* đánh theo chỉ
số item, nhưng đó thuần túy là mẹo tăng tốc — mô hình chỉ nhìn thấy **vector đặc
trưng**, không bao giờ nhìn thấy chỉ số. Lúc phục vụ thì gọi thẳng
`features.token_features(word, pos)`, không cần bảng nào cả.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from src import dkt as _dkt  # noqa: E402
from src.dkt import WindowDataset, collate, load_sequences, save_results  # noqa: E402
from src.features import FEATURE_DIM, build_matrix  # noqa: E402
from src.history_features import HISTORY_DIM, sequence_history  # noqa: E402

MODEL_KEY = "dkt_feat"


class HistoryWindowDataset(WindowDataset):
    """Như `WindowDataset` nhưng kèm đặc trưng lịch sử người-học × từ.

    Tính MỘT LẦN trên chuỗi đầy đủ của mỗi user rồi mới cắt cửa sổ. Tính trong
    từng cửa sổ sẽ mất phần lịch sử nằm trước cửa sổ đó — người học đã gặp từ
    này 10 lần ở đầu chuỗi mà cửa sổ lại tưởng là lần đầu.
    """

    #: Cứ 5 người học giữ lại 1 để đánh giá cold-start. Chia theo NGƯỜI chứ
    #: không theo thời gian: SLAM chia tập theo thời gian nên lượt trả lời đầu
    #: đời của mọi người đều nằm trong giai đoạn train — dev/test có đúng 0 mẫu,
    #: tức là không có cách nào kiểm chứng năng lực này bằng cách chia sẵn có.
    HOLDOUT_EVERY = 5

    def __init__(self, data: dict, max_len: int, stride: int,
                 coldstart_holdout: bool = False):
        super().__init__(data, max_len, stride)
        self.coldstart_holdout = coldstart_holdout
        # `days` là trường thêm sau; dữ liệu tiền xử lý cũ không có nó. Thiếu thì
        # chiều elapsed_days về 0 chứ không nổ — nhưng khi đó mô hình mù thời
        # gian trở lại, nên chạy lại preprocess mới có ý nghĩa.
        self.history = [
            sequence_history(seq["items"], seq["corrects"], seq.get("days"))
            for seq in self.data
        ]
        self.formats = [seq["formats"] for seq in self.data]

    def __getitem__(self, i):
        base = super().__getitem__(i)
        ui, start, end, _score_from = self.index[i]
        # Vị trí 0 chỉ ĐÁNG chấm khi cửa sổ bắt đầu từ đầu chuỗi — khi đó nó
        # thật sự là lượt trả lời đầu đời của người học. Với cửa sổ ở giữa
        # chuỗi thì người học CÓ lịch sử, ta chỉ vừa cắt nó đi; chấm ở đó là dạy
        # mô hình một điều sai.
        first = np.zeros(end - start, dtype=bool)
        held = np.zeros(end - start, dtype=bool)
        if start == 0:
            if self.coldstart_holdout and ui % self.HOLDOUT_EVERY == 0:
                held[0] = True     # để dành đánh giá, KHÔNG cho vào loss
            else:
                first[0] = True
        return (*base, torch.from_numpy(self.history[ui][start:end]),
                torch.from_numpy(first),
                torch.from_numpy(self.formats[ui][start:end].copy()),
                torch.from_numpy(held))


def collate_history(batch):
    """Gộp batch: dùng lại `collate` cũ rồi nối thêm cột lịch sử đã đệm."""
    stacked = collate([b[:5] for b in batch])
    lmax = stacked[0].shape[1]
    hist = torch.zeros((len(batch), lmax, HISTORY_DIM), dtype=torch.float32)
    first = torch.zeros((len(batch), lmax), dtype=torch.bool)
    fmt = torch.full((len(batch), lmax), config.FORMAT_OTHER, dtype=torch.long)
    held = torch.zeros((len(batch), lmax), dtype=torch.bool)
    for i, b in enumerate(batch):
        h = b[5]
        hist[i, : len(h)] = h
        first[i, : len(b[6])] = b[6]
        fmt[i, : len(b[7])] = b[7]
        held[i, : len(b[8])] = b[8]
    return (*stacked, hist, first, fmt, held)


# ---------------------------------------------------------------- đặc trưng
def build_feature_table(item2idx: dict[str, int]) -> torch.Tensor:
    """Bảng (vocab, FEATURE_DIM) — đặc trưng của từng token trong vocab huấn luyện.

    `<PAD>`/`<UNK>` để vector 0: chúng không phải từ thật, không có đặc điểm gì.
    """
    token_pos = {}
    pos_path = config.PROCESSED_DIR / "token_pos.json"
    if pos_path.exists():
        token_pos = json.loads(pos_path.read_text(encoding="utf-8"))

    tokens = [""] * len(item2idx)
    for tok, idx in item2idx.items():
        tokens[idx] = "" if tok.startswith("<") else tok

    matrix = build_matrix(tokens, token_pos)
    for tok, idx in item2idx.items():
        if tok.startswith("<"):
            matrix[idx] = 0.0
    return torch.from_numpy(matrix)


# ---------------------------------------------------------------- model
class FeatureDKT(nn.Module):
    """LSTM trên chuỗi (đặc trưng từ × kết quả), chấm bằng đặc trưng của từ kế tiếp."""

    def __init__(self, n_feat: int, emb_dim: int, hidden: int, num_layers: int, dropout: float):
        super().__init__()
        # Tách đặc trưng theo kết quả đúng/sai — đây là bản tổng quát của mẹo
        # `2*item + correct` trong DKT gốc: cùng một từ, trả lời đúng hay sai
        # phải cho hai tín hiệu khác nhau.
        self.in_proj = nn.Linear(2 * n_feat, emb_dim)
        self.drop = nn.Dropout(dropout)
        self.lstm = nn.LSTM(emb_dim, hidden, num_layers=num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        # Đầu ra một số duy nhất cho CẶP (trạng thái người học, từ cần chấm) —
        # thay cho một chiều riêng cho mỗi từ. Đây là chỗ vocab biến mất.
        self.scorer = nn.Sequential(
            nn.Linear(hidden + n_feat, hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, feats: torch.Tensor, corrects: torch.Tensor) -> torch.Tensor:
        """feats (B,L,F) · corrects (B,L) -> logit (B,L) cho MỌI bước 0..L-1.

        Bước 0 chấm bằng **trạng thái khởi tạo** của LSTM (toàn 0) — nghĩa là dự
        đoán chỉ dựa vào đặc điểm của từ, chưa biết gì về người học. Đó chính là
        tình huống người học mới tinh trả lời câu đầu tiên. Bản theo ID không làm
        được điều này: đầu vào bước t của nó đã chứa sẵn kết quả của bước t.
        """
        c = corrects.unsqueeze(-1).float()
        x = self.in_proj(torch.cat([feats * (1.0 - c), feats * c], dim=-1))
        h, _ = self.lstm(self.drop(x))

        zero = torch.zeros(h.size(0), 1, h.size(2), dtype=h.dtype, device=h.device)
        state = torch.cat([zero, h[:, :-1, :]], dim=1)   # trạng thái TRƯỚC mỗi bước
        return self.scorer(torch.cat([self.drop(state), feats], dim=-1)).squeeze(-1)


def _scored(logit, corrects, splits, cand, phase_code, first=None, only_first=False):
    """Các vị trí được chấm. Hai tập TÁCH BẠCH:

    * mặc định: vị trí >= 1 — đúng tập mà bản theo ID chấm, để so sánh công bằng;
    * `only_first=True`: riêng vị trí 0 của những người học chưa có lịch sử nào —
      năng lực mà bản theo ID không có.
    """
    in_phase = splits == phase_code
    if only_first:
        if first is None:
            empty = logit.new_empty(0)
            return empty, empty
        mask = first & in_phase
    else:
        mask = torch.zeros_like(in_phase)
        mask[:, 1:] = cand[:, 1:] & in_phase[:, 1:]
    return logit[mask], corrects.float()[mask]


def _batch_feats(batch, table, device, use_history):
    """Ghép ba nhóm đặc trưng của mỗi bước.

    1. tĩnh — thuộc tính của TỪ (CEFR, từ loại, độ dài, tần suất);
    2. lịch sử — quan hệ NGƯỜI HỌC × TỪ (số lần gặp, recency...);
    3. dạng bài — loại BÀI TẬP của chính bước đó.

    Nhóm 3 hợp lệ vì lúc dự đoán ta đã biết sắp ra bài dạng nào; nó không phải
    thông tin từ tương lai.
    """
    items = batch[1].to(device)
    feats = table[items]
    if use_history:
        feats = torch.cat([feats, batch[5].to(device)], dim=-1)
    if len(batch) > 7:
        fmt = torch.nn.functional.one_hot(
            batch[7].to(device), num_classes=config.FORMAT_DIM
        ).float()
        feats = torch.cat([feats, fmt], dim=-1)
    return feats


def run_eval(model, loader, table, device, phase_code, use_history,
             only_first=False, holdout=False):
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for batch in loader:
            corrects = batch[2].to(device)
            splits = batch[3].to(device); cand = batch[4].to(device)
            mask_src = 8 if holdout else 6
            first = batch[mask_src].to(device) if len(batch) > mask_src else None
            logit = model(_batch_feats(batch, table, device, use_history), corrects)
            g, t = _scored(logit, corrects, splits, cand, phase_code, first, only_first)
            if g.numel():
                ps.append(torch.sigmoid(g).cpu().numpy())
                ys.append(t.cpu().numpy())
    if not ys:
        return {"auc": float("nan"), "accuracy": float("nan"), "n": 0}
    from src.evaluate import evaluate

    return evaluate(np.concatenate(ys), np.concatenate(ps))


# ---------------------------------------------------------------- train
def train(subset: bool, tag: str, use_history: bool = True,
          epochs: int | None = None, coldstart_holdout: bool = False) -> dict:
    cfg = dict(config.CONFIG)
    if epochs:
        cfg["epochs"] = epochs
    config.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    item2idx = json.loads((config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8"))
    table = build_feature_table(item2idx).to(device)

    # `collate` dùng chung với dkt.py và nó đọc hai biến toàn cục này để dựng
    # cột `inp`. Bản feature-based KHÔNG dùng `inp` (đó chính là điểm khác biệt),
    # nhưng vẫn phải đặt cho hàm dùng chung chạy được.
    _dkt.VOCAB = len(item2idx)
    _dkt.PAD_INPUT = 2 * len(item2idx)

    data = load_sequences(subset)
    if use_history:
        ds = HistoryWindowDataset(data, cfg["max_seq_len"], cfg["stride"],
                                  coldstart_holdout=coldstart_holdout)
        fn = collate_history
    else:
        ds = WindowDataset(data, cfg["max_seq_len"], cfg["stride"])
        fn = collate
    g = torch.Generator(); g.manual_seed(config.SEED)
    train_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=True,
                              collate_fn=fn, generator=g)
    eval_loader = DataLoader(ds, batch_size=cfg["batch_size"], shuffle=False, collate_fn=fn)

    n_feat = FEATURE_DIM + (HISTORY_DIM if use_history else 0) + config.FORMAT_DIM
    model = FeatureDKT(n_feat, cfg["embedding_dim"], cfg["hidden_dim"],
                       cfg["num_layers"], cfg["dropout"]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"])
    bce = nn.BCEWithLogitsLoss()

    best_dev = -1.0; best_state = None; best_epoch = -1; no_improve = 0
    t0 = time.time()
    print(f"[DKT-feat/{tag}] users={len(data)} windows={len(ds)} feat_dim={n_feat} "
          f"(tĩnh {FEATURE_DIM}"
          f"{f' + lịch sử {HISTORY_DIM}' if use_history else ', KHÔNG dùng lịch sử'}"
          f" + dạng bài {config.FORMAT_DIM})"
          f" — vocab KHÔNG vào mô hình · device={device.type}")

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        total_loss = 0.0; nb = 0
        for batch in train_loader:
            corrects = batch[2].to(device)
            splits = batch[3].to(device); cand = batch[4].to(device)
            first = batch[6].to(device) if len(batch) > 6 else None
            logit = model(_batch_feats(batch, table, device, use_history), corrects)
            code = config.SPLIT2CODE["train"]
            g_logit, target = _scored(logit, corrects, splits, cand, code)
            # Gộp thêm vị trí 0 vào loss: không huấn luyện ở đó thì lúc phục vụ
            # chấm người học mới là chấm bừa trên vùng mô hình chưa từng thấy.
            f_logit, f_target = _scored(logit, corrects, splits, cand, code, first, True)
            if f_logit.numel():
                g_logit = torch.cat([g_logit, f_logit])
                target = torch.cat([target, f_target])
            if g_logit.numel() == 0:
                continue
            loss = bce(g_logit, target)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip"])
            opt.step()
            total_loss += float(loss); nb += 1

        tr = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["train"], use_history)
        dv = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["dev"], use_history)
        print(f"  epoch {epoch:>2} loss={total_loss / max(nb, 1):.4f} "
              f"train-AUC={tr['auc']:.4f} dev-AUC={dv['auc']:.4f}")

        if dv["auc"] > best_dev:
            best_dev = dv["auc"]; best_epoch = epoch; no_improve = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            no_improve += 1
            if no_improve >= cfg["patience"]:
                print(f"  early stop ở epoch {epoch} (tốt nhất: {best_epoch})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    test = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["test"], use_history)
    # Cold-start chấm trên phần GIỮ LẠI (nếu bật) — đó là mẫu mô hình chưa từng
    # thấy. Không bật thì vẫn chấm như cũ, nhưng số đó là in-sample nên vô nghĩa.
    cold = run_eval(model, eval_loader, table, device, config.SPLIT2CODE["train"],
                    use_history, only_first=True, holdout=coldstart_holdout)

    # Thử nghiệm phải ghi ra file RIÊNG. Dùng chung tên với bản production thì
    # một lần chạy ablation là mất trọng số đang phục vụ — đúng lỗi đã mắc một lần.
    suffix = "" if use_history else "_static"
    if coldstart_holdout:
        suffix += "_coldholdout"
    if subset:
        suffix += "_subset"
    ckpt = config.MODELS_DIR / f"{MODEL_KEY}{suffix}_best.pt"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "config": cfg,
        "feature_dim": n_feat,
        "use_history": use_history,
        "model": MODEL_KEY,
    }, ckpt)

    metrics = {
        "dev_auc": round(float(best_dev), 4),
        "test_auc": round(float(test["auc"]), 4),
        "test_accuracy": round(float(test["accuracy"]), 4),
        "test_n": int(test["n"]),
        # Năng lực bản theo ID KHÔNG có: dự đoán lượt đầu đời của người học,
        # chỉ dựa trên đặc điểm của từ. Mẫu ít (một lượt/người) nên đọc dè dặt.
        "coldstart_auc": None if cold["n"] == 0 else round(float(cold["auc"]), 4),
        "coldstart_n": int(cold["n"]),
        "coldstart_heldout": coldstart_holdout,
        "best_epoch": best_epoch,
        "seconds": round(time.time() - t0, 1),
        "feature_dim": n_feat,
        "use_history": use_history,
    }
    print(f"[DKT-feat/{tag}] dev-AUC={metrics['dev_auc']} test-AUC={metrics['test_auc']} "
          f"({metrics['seconds']}s) -> {ckpt}")
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subset", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--epochs", type=int, default=None,
                    help="ghi đè số epoch (bản feature-based hội tụ chậm hơn bản ID)")
    ap.add_argument("--holdout-coldstart", action="store_true",
                    help="giữ lại 1/5 người học để ĐÁNH GIÁ được cold-start")
    ap.add_argument("--no-history", action="store_true",
                    help="ablation: chỉ dùng đặc trưng tĩnh của từ, bỏ lịch sử")
    args = ap.parse_args()
    if not (args.subset or args.full):
        ap.error("chọn --subset hoặc --full")

    tag = "subset" if args.subset else "full"
    use_history = not args.no_history
    metrics = train(subset=args.subset, tag=tag, use_history=use_history,
                    epochs=args.epochs, coldstart_holdout=args.holdout_coldstart)
    key = f"{tag}{'' if use_history else '_static'}"
    if args.holdout_coldstart:
        key += "_coldholdout"
    save_results(key, metrics, group=MODEL_KEY)


if __name__ == "__main__":
    config.use_utf8_console()
    main()
