"""UC-68 — phục vụ DKT **feature-based**.

Khác `src/serve.py` ở chỗ quan trọng nhất: **không có vocab.** `DKTServer` cũ tra
`item2idx` và trả `None` cho mọi từ ngoài đó — đo trên thư viện thật thì 76% số từ
rơi vào nhánh này. Bản feature-based mô tả từ bằng đặc điểm nên chấm được từ nào
cũng được, miễn tính được vector.

Đầu vào giống hệt bản cũ (`history`, `targets`) nên backend không phải sửa gì;
thêm tùy chọn `pos` để truyền từ loại — có thì tốt hơn, không có vẫn chạy.
"""
from __future__ import annotations

import json
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from src.dkt_feat import FeatureDKT  # noqa: E402
from src.features import FEATURE_DIM, format_code, token_features  # noqa: E402
from src.history_features import (  # noqa: E402
    LOG_DAYS, LOG_GAP, LOG_SEEN, HISTORY_DIM, WITH_ELAPSED_DAYS, sequence_history,
)  # noqa: E402


class FeatureDKTServer:
    """Nạp `dkt_feat_best.pt` và chấm P(trả lời đúng) cho từ BẤT KỲ."""

    name = "dkt_feat"

    def __init__(self, ckpt_path: Path | None = None):
        ckpt_path = ckpt_path or (config.MODELS_DIR / "dkt_feat_best.pt")
        if not ckpt_path.exists():
            raise FileNotFoundError(
                f"Chưa có checkpoint {ckpt_path} — train trước: "
                "python src/dkt_feat.py --full"
            )

        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        cfg = ckpt.get("config", config.CONFIG)
        self.use_history: bool = bool(ckpt.get("use_history", True))
        self.feature_dim: int = int(
            ckpt.get("feature_dim", FEATURE_DIM + (HISTORY_DIM if self.use_history else 0))
        )
        expected = (FEATURE_DIM + (HISTORY_DIM if self.use_history else 0)
                    + config.FORMAT_DIM)
        if self.feature_dim != expected:
            # Lệch số chiều là hỏng ÂM THẦM: model vẫn nạp, vẫn trả số, chỉ là
            # đọc sai cột. Phải chết to ngay lúc khởi động.
            raise RuntimeError(
                f"Checkpoint {ckpt_path.name} có {self.feature_dim} chiều đặc trưng "
                f"nhưng bộ tính hiện tại sinh ra {expected}. Bộ đặc trưng đã đổi "
                "kể từ lần train — phải train lại: python src/dkt_feat.py --full"
            )

        self.max_len = config.CONFIG["max_seq_len"]

        self.model = FeatureDKT(self.feature_dim, cfg["embedding_dim"], cfg["hidden_dim"],
                                cfg["num_layers"], cfg["dropout"])
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    # ------------------------------------------------------------------ helpers
    def _static_row(self, token: str, pos: dict[str, str]) -> np.ndarray:
        return token_features(token, pos.get(token))

    def _format_row(self, name: str | None) -> np.ndarray:
        vec = np.zeros(config.FORMAT_DIM, dtype=np.float32)
        vec[format_code(name)] = 1.0
        return vec

    def _history_rows(
        self, tokens: list[str], corrects: list[int], formats: list[str | None],
        pos: dict[str, str], days: list[float] | None = None,
    ) -> tuple[np.ndarray, dict[str, tuple[int, int, int, int, float]]]:
        """Đặc trưng của phần LỊCH SỬ + bảng thống kê theo từ.

        Tính MỘT LẦN cho cả lượt gọi. Trước đây hàm này chạy lại cho từng target;
        với 50 target trên lịch sử 1.000 bước là 50.000 lượt tính đặc trưng, và
        backend hết hạn chờ 5 giây rồi rơi về prior — nghĩa là DKT coi như không
        tồn tại, mà không có lỗi nào hiện ra.
        """
        if not tokens:
            return np.zeros((0, self.feature_dim), dtype=np.float32), {}

        parts = [np.stack([self._static_row(t, pos) for t in tokens])]
        if self.use_history:
            ids = np.array([hash(t) % (2**31) for t in tokens], dtype=np.int64)
            day_arr = None if days is None else np.asarray(days, dtype=np.float64)
            parts.append(sequence_history(
                ids, np.asarray(corrects, dtype=np.int64), day_arr,
            ))
        parts.append(np.stack([self._format_row(f) for f in formats]))
        rows = np.concatenate(parts, axis=1).astype(np.float32)

        # (số lần gặp, số lần đúng, vị trí gần nhất, kết quả gần nhất, MỐC NGÀY
        # gần nhất) theo TỪ. Mốc ngày để tính `elapsed_days` cho bước sắp chấm.
        stats: dict[str, tuple[int, int, int, int, float]] = {}
        for i, (token, correct) in enumerate(zip(tokens, corrects)):
            count, n_ok, _, _, _ = stats.get(token, (0, 0, -1, 0, 0.0))
            day_i = 0.0 if days is None else float(days[i])
            stats[token] = (count + 1, n_ok + int(correct), i, int(correct), day_i)
        return rows, stats

    def _target_row(
        self, target: str, pos: dict[str, str], target_format: str | None,
        stats: dict[str, tuple[int, int, int, int, float]], length: int,
        target_day: float | None = None,
    ) -> np.ndarray:
        """Một hàng đặc trưng cho bước SẮP chấm — O(1) nhờ bảng thống kê."""
        parts = [self._static_row(target, pos)]
        if self.use_history:
            hist = np.zeros(HISTORY_DIM, dtype=np.float32)
            entry = stats.get(target)
            if entry is None:
                # Giống hệt `sequence_history`: chưa gặp thì "không biết" (0.5),
                # KHÔNG phải "sai" (0).
                hist[:] = (0.0, 0.5, 0.0, 1.0, 0.5, 0.0)[:HISTORY_DIM]
            else:
                count, n_ok, last_pos, last_ok, last_day = entry
                hist[0] = min(math.log1p(count) / LOG_SEEN, 1.0)
                hist[1] = n_ok / count
                hist[2] = min(math.log1p(length - last_pos) / LOG_GAP, 1.0)
                hist[3] = 0.0
                hist[4] = float(last_ok)
                if WITH_ELAPSED_DAYS and target_day is not None:
                    hist[5] = min(
                        math.log1p(max(0.0, target_day - last_day)) / LOG_DAYS, 1.0,
                    )
            parts.append(hist)
        parts.append(self._format_row(target_format))
        return np.concatenate(parts).astype(np.float32)

    @torch.no_grad()
    def _score_many(self, window: np.ndarray, corrects: list[int], targets: np.ndarray) -> np.ndarray:
        """Chấm NHIỀU từ cùng một lịch sử — cho kết quả như chạy cả cửa sổ cho TỪNG từ.

        Trong `FeatureDKT.forward`, logit bước cuối chỉ dùng trạng thái LSTM của
        bước TRƯỚC đó cộng đặc trưng của từ cần chấm; đầu vào LSTM của chính bước
        cuối không ảnh hưởng tới nó. Vậy chạy LSTM một lần trên phần lịch sử rồi
        đưa cả lô đặc trưng qua `scorer` là đủ. Bản cũ chạy lại LSTM trên cả cửa
        sổ cho TỪNG từ: 400 từ đến hạn = 400 lượt LSTM, ~2,5 giây mỗi lần mở lịch.
        """
        model = self.model
        if len(window):
            feats = torch.from_numpy(window[None, ...])
            c = torch.tensor([corrects[-len(window):]], dtype=torch.float32).unsqueeze(-1)
            h, _ = model.lstm(model.in_proj(torch.cat([feats * (1.0 - c), feats * c], dim=-1)))
            state = h[0, -1]
        else:
            # Chưa có lịch sử: trạng thái khởi tạo toàn 0, như bước 0 lúc train.
            state = torch.zeros(model.lstm.hidden_size)
        tgt = torch.from_numpy(targets)
        logits = model.scorer(torch.cat([state.expand(len(tgt), -1), tgt], dim=-1)).squeeze(-1)
        return torch.sigmoid(logits).numpy()

    # ------------------------------------------------------------------ API
    def predict_mastery(
        self,
        history: list[tuple[str, int]],
        targets: list[str],
        pos: dict[str, str] | None = None,
        history_formats: list[str] | None = None,
        target_format: str | None = None,
        history_days: list[float] | None = None,
        target_day: float | None = None,
    ) -> dict[str, float | None]:
        """P(trả lời đúng) cho từng target.

        **Lịch sử rỗng vẫn chấm được** (người học mới tinh): mô hình dùng trạng
        thái khởi tạo của LSTM, tức dự đoán chỉ dựa trên đặc điểm của từ. Bản
        theo ID không làm được vì đầu vào bước t của nó đã chứa kết quả bước t.

        Năng lực này ĐÃ đo được, bằng cách giữ hẳn 1/5 người học ra khỏi tập
        train rồi chỉ chấm lượt trả lời đầu tiên của họ (`--holdout-coldstart`):
        AUC **0,7487** trên 519 người. Thấp hơn 0,8378 của người đã có lịch sử —
        đúng như kỳ vọng, vì lượt đầu chỉ còn đặc trưng của từ để dựa vào — nhưng
        vẫn cao hơn BKT (0,7228) chấm với đầy đủ lịch sử.

        Đừng lấy con số 0,8028 đo thẳng trên tập test: SLAM chia theo thời gian
        nên những người học ấy đã nằm trong tập train, đo như vậy là tự chấm bài
        mình. Bản thử trên 60 người cho 0,8246 cũng là ảo vì mẫu quá nhỏ.
        """
        if not targets:
            return {}

        pos_map = {k: v for k, v in (pos or {}).items() if v}
        hist_tokens = [str(t) for t, _ in history]
        hist_corrects = [int(c) for _, c in history]
        # Dạng bài của từng lượt trong lịch sử; thiếu thì để None -> mã "other".
        raw = list(history_formats or [])
        hist_formats: list[str | None] = raw + [None] * (len(hist_tokens) - len(raw))

        # Đặc trưng lịch sử tính trên TOÀN BỘ lịch sử nhận được, RỒI mới cắt cho
        # vừa cửa sổ LSTM. Đây là chỗ rất dễ lệch train/serve: lúc huấn luyện,
        # `sequence_history` chạy trên cả chuỗi của người học rồi mới cắt cửa sổ.
        # Nếu ở đây cắt trước rồi mới đếm thì "đã gặp bao nhiêu lần" và "lần gần
        # nhất cách bao xa" đều nhỏ đi — một người học 1.300 lượt sẽ bị đối xử
        # như người mới. API vẫn 200, số vẫn có, chỉ là sai.
        # `history_days`/`target_day`: mốc thời gian (số ngày, gốc tùy ý miễn là
        # nhất quán) để tính `elapsed_days`. Thiếu thì chiều đó về 0 và mô hình
        # mù thời gian — vẫn chấm được "từ này người này có nắm không", nhưng
        # KHÔNG trả lời được "bao giờ thì quên", nên đừng lập lịch dựa vào nó.
        hist_days = list(history_days or []) or None
        if hist_days is not None and len(hist_days) < len(hist_tokens):
            hist_days = hist_days + [hist_days[-1]] * (len(hist_tokens) - len(hist_days))

        hist_rows, stats = self._history_rows(
            hist_tokens, hist_corrects, hist_formats, pos_map, hist_days
        )
        # Cắt phần lịch sử cho vừa cửa sổ LSTM SAU khi đã đếm xong (thứ tự này
        # đúng như lúc huấn luyện), chừa một chỗ cho bước sắp chấm.
        window = hist_rows[-(self.max_len - 1):] if self.max_len > 1 else hist_rows[:0]
        corrects = hist_corrects[-len(window):] + [0]

        target_rows = np.stack([
            self._target_row(target, pos_map, target_format, stats, len(hist_tokens), target_day)
            for target in targets
        ])
        probs = self._score_many(window, corrects[:-1], target_rows)
        return {target: float(p) for target, p in zip(targets, probs)}


@lru_cache(maxsize=1)
def get_server() -> FeatureDKTServer:
    """Singleton — nạp model một lần."""
    return FeatureDKTServer()


# ------------------------------------------------------------------ self-test
#: Sai lệch tối đa chấp nhận được giữa AUC qua đường phục vụ và AUC lúc train.
#: Mẫu khác nhau (120 người học so với 2.593) nên chênh vài phần nghìn là bình
#: thường; chênh tới mức này thì gần như chắc chắn là skew, không phải nhiễu.
SKEW_TOLERANCE = 0.02


def _self_test(sample_users: int = 120) -> int:
    """Chứng minh SERVICE tái hiện đúng mô hình đã huấn luyện.

    Vì sao cần: giữa lúc train và lúc phục vụ có rất nhiều chỗ để lệch âm thầm —
    thứ tự chiều đặc trưng, thiếu từ loại, thiếu dạng bài, cắt lịch sử khác nhau.
    Mọi lệch kiểu đó đều KHÔNG gây lỗi: API vẫn 200, mastery vẫn có số, chỉ là
    sai. Cách duy nhất phát hiện là chấm lại tập test qua đúng đường phục vụ rồi
    so với AUC lúc train.

    Chạy (từ ml/):  python -m src.serve_feat
    Trả 0 nếu khớp AUC lúc train trong biên `SKEW_TOLERANCE`, 1 nếu lệch — dùng
    được như một cổng chặn trước khi triển khai.
    """
    import pickle

    from src.evaluate import evaluate

    srv = get_server()
    item2idx = json.loads(
        (config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8")
    )
    idx2token = {v: k for k, v in item2idx.items()}
    code2format = {v: k for k, v in config.FORMAT2CODE.items()}
    token_pos: dict[str, str] = {}
    pos_path = config.PROCESSED_DIR / "token_pos.json"
    if pos_path.exists():
        token_pos = json.loads(pos_path.read_text(encoding="utf-8"))

    with open(config.PROCESSED_DIR / "sequences.pkl", "rb") as fh:
        data = pickle.load(fh)

    test_code = config.SPLIT2CODE["test"]
    users = sorted(data.keys())[:sample_users]

    y_true: list[int] = []
    y_prob: list[float] = []
    for user in users:
        seq = data[user]
        items = seq["items"].tolist()
        corrects = seq["corrects"].tolist()
        splits = seq["splits"].tolist()
        formats = seq["formats"].tolist() if "formats" in seq else [config.FORMAT_OTHER] * len(items)

        for t in range(1, len(items)):
            if splits[t] != test_code:
                continue
            hist = [(idx2token[i], c) for i, c in zip(items[:t], corrects[:t])]
            hist_fmt = [code2format.get(f, "") for f in formats[:t]]
            target = idx2token[items[t]]
            # Từ loại cho TOÀN BỘ token, không riêng target: lúc huấn luyện mọi
            # bước đều có từ loại thật, gửi thiếu là lệch ngay ở đầu vào.
            pos_map = {tok: token_pos.get(tok, "") for tok, _ in hist}
            pos_map[target] = token_pos.get(target, "")
            scored = srv.predict_mastery(
                hist, [target],
                pos=pos_map,
                history_formats=hist_fmt,
                target_format=code2format.get(formats[t], ""),
            )
            value = scored.get(target)
            if value is None:
                continue
            y_true.append(int(corrects[t]))
            y_prob.append(float(value))

    if not y_true:
        print("[serve-feat self-test] không có mẫu test nào — bỏ qua")
        return 1

    metrics = evaluate(np.array(y_true), np.array(y_prob))
    served = float(metrics["auc"])

    trained: float | None = None
    results = config.MODELS_DIR / "results.json"
    if results.exists():
        trained = (
            json.loads(results.read_text(encoding="utf-8"))
            .get("dkt_feat", {}).get("full", {}).get("test_auc")
        )

    print(f"[serve-feat self-test] {len(users)} user | n={metrics['n']:,} | "
          f"AUC={served:.4f} ACC={metrics['accuracy']:.4f}")
    if trained is None:
        print("  Chưa có test-AUC lúc train để đối chiếu (models/results.json).")
        return 0

    gap = served - trained
    print(f"  AUC lúc train: {trained:.4f} · chênh {gap:+.4f} "
          f"(biên cho phép ±{SKEW_TOLERANCE})")
    if abs(gap) <= SKEW_TOLERANCE:
        print("  ĐẠT — đường phục vụ tái hiện đúng mô hình đã huấn luyện.")
        return 0

    print("  LỆCH — đường phục vụ KHÔNG khớp mô hình. Đây gần như chắc chắn là")
    print("  skew chứ không phải nhiễu. Chỗ hay hỏng nhất, theo thứ tự:")
    print("    1. thiếu từ loại hoặc dạng bài cho một phần chuỗi;")
    print("    2. đặc trưng lịch sử tính sau khi đã cắt cửa sổ (phải tính TRƯỚC);")
    print("    3. thứ tự các nhóm chiều trong vector khác lúc train.")
    return 1


if __name__ == "__main__":
    config.use_utf8_console()
    sys.exit(_self_test())
