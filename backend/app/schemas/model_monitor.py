"""UC-70 — giám sát hiệu năng mô hình."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ModelHealth(BaseModel):
    model_config = {"protected_namespaces": ()}   # cho phép field bắt đầu bằng model_

    model_name: str
    sample_size: int
    lookback_days: int
    # None khi mẫu chưa đủ — trả None thay vì số 0 để không bị đọc nhầm là "kém"
    accuracy: float | None
    brier: float | None
    #: Tỉ lệ trả lời đúng thực tế — bộ "đoán theo lớp đa số". Mô hình không vượt
    #: được số này thì accuracy cao cũng không nói lên điều gì.
    baseline_accuracy: float | None = None
    #: Tỉ lệ state ĐÃ có tương tác mà mô hình thực sự chấm được (không tính các
    #: từ người học chưa động tới).
    coverage: float
    covered_states: int = 0
    answered_states: int = 0
    #: Tỉ lệ từ trong thư viện mà service đang phục vụ biết. None = service không
    #: sẵn sàng (khác hẳn với 0%).
    vocab_coverage: float | None = None
    reliable: bool
    note: str


class MetricPoint(BaseModel):
    metric: str
    value: float
    sample_size: int
    recorded_at: datetime
