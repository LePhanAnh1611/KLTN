"""Cấu hình nghiên cứu DKT (dùng chung cho notebooks & src).

Import: `from config import CONFIG, set_seed` (chạy từ thư mục ml/),
hoặc thêm ml/ vào sys.path trong notebook.
"""
from __future__ import annotations

import random
from pathlib import Path

# ---- Đường dẫn ----
ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
SLAM_DIR = DATA_DIR / "data_en_es"          # dataset SLAM en_es gốc
SLAM_BASE = "en_es.slam.20190204"           # tiền tố tên file train/dev/test

# Dạng bài mà SLAM ghi sẵn ở dòng metadata `format:`. Ba dạng này khác nhau về
# BẢN CHẤT nhận thức, nên là đặc trưng thật chứ không phải siêu dữ liệu trang trí:
#   reverse_tap       - chạm vào ô đáp án có sẵn      -> NHẬN DIỆN
#   reverse_translate - tự gõ lại                     -> NHỚ CHỦ ĐỘNG
#   listen            - nghe rồi gõ lại               -> NGHE + SẢN SINH
FORMAT2CODE = {"reverse_tap": 0, "reverse_translate": 1, "listen": 2}
FORMAT_OTHER = 3
FORMAT_DIM = 4
PROCESSED_DIR = DATA_DIR / "processed"      # đầu ra tiền xử lý
MODELS_DIR = ML_DIR / "models"
NOTEBOOKS_DIR = ML_DIR / "notebooks"
SRC_DIR = ML_DIR / "src"

# ---- Tái lập ----
SEED = 42

# ---- Chỉ số item đặc biệt ----
PAD_IDX = 0
UNK_IDX = 1
SPLIT2CODE = {"train": 0, "dev": 1, "test": 2}

# ---- Siêu tham số (placeholder cho DKT/SAKT, chỉnh khi train thật) ----
CONFIG = {
    "seed": SEED,
    "data_dir": str(DATA_DIR),
    "models_dir": str(MODELS_DIR),
    # huấn luyện
    "batch_size": 64,
    "learning_rate": 1e-3,
    "epochs": 20,             # DKT: 20 + early stopping (CPU-friendly)
    "patience": 5,            # early stopping theo dev-AUC
    "grad_clip": 5.0,         # clip_grad_norm_ max_norm
    "max_seq_len": 200,       # độ dài cửa sổ tối đa (L)
    "stride": 100,            # bước trượt cửa sổ (chồng lấn L-stride làm warm-up)
    "train_ratio": 0.8,       # phần train trong split
    # tiền xử lý
    "lowercase_tokens": False,  # giữ nguyên hoa/thường của token (item)
    "subset_users": 300,        # số user trong subset debug
    # kiến trúc DKT (LSTM)
    "embedding_dim": 100,     # embedding cặp <item, đúng/sai>
    "hidden_dim": 100,        # hidden state của LSTM (100 cho CPU)
    "num_layers": 1,
    "dropout": 0.2,
    # kiến trúc SAKT (self-attention)
    "nhead": 4,               # số attention head (d_model=embedding_dim chia hết)
    "dim_feedforward": 128,   # fe-forward trong Transformer layer
    # thiết bị: "cuda" nếu có GPU, ngược lại "cpu" (đặt lúc train)
    "device": "cpu",
}


def set_seed(seed: int = SEED) -> None:
    """Cố định seed cho random / numpy / torch để tái lập kết quả."""
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def use_utf8_console() -> None:
    """Ép stdout/stderr sang UTF-8 trước khi in tiếng Việt.

    Console Windows mặc định là cp1252. In một dòng có dấu sẽ ném
    UnicodeEncodeError — thường ở đúng dòng tổng kết, tức SAU khi công việc đã
    xong xuôi, nên nhìn như script thất bại trong khi nó đã thành công, và mã
    thoát khác 0 làm mọi cổng chặn báo hỏng vì lý do chẳng liên quan.

    Gọi ở đầu khối `if __name__ == "__main__"` của từng script.
    """
    import sys

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
