"""Hàm đánh giá dùng chung cho BKT / DKT / SAKT — đảm bảo so sánh công bằng.

Mọi mô hình đưa về (y_true, y_prob) rồi gọi evaluate() để lấy cùng bộ metric.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, roc_auc_score


def evaluate(y_true, y_prob, threshold: float = 0.5) -> dict:
    """Tính AUC-ROC và Accuracy từ nhãn thật và xác suất dự đoán P(correct).

    y_true: mảng 0/1. y_prob: mảng xác suất [0,1]. Trả dict {auc, accuracy, n}.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    n = int(len(y_true))
    if n == 0:
        return {"auc": float("nan"), "accuracy": float("nan"), "n": 0}

    # AUC cần cả 2 lớp xuất hiện
    if len(np.unique(y_true)) < 2:
        auc = float("nan")
    else:
        auc = float(roc_auc_score(y_true, y_prob))

    acc = float(accuracy_score(y_true, (y_prob >= threshold).astype(int)))
    return {"auc": auc, "accuracy": acc, "n": n}
