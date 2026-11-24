"""M4 slice 2 — UC-68: service REST phục vụ DKT (nội bộ, backend gọi qua HTTP).

Chạy local (từ ml/):  uvicorn serve_app:app --port 8001
Docker: xem docker-compose service `ml-serve`.

Hai biến thể mô hình, chọn bằng biến môi trường `DKT_VARIANT`:

* `feature` (mặc định) — DKT feature-based (`src/dkt_feat.py`). Mô tả từ bằng
  đặc điểm nên chấm được **từ bất kỳ**, kể cả từ vừa cắt từ PDF hôm nay.
* `id` — DKT gốc theo chỉ số item (`src/dkt.py`). Giữ lại làm đường lùi và làm
  mốc so sánh cho chương thực nghiệm; nó trả `None` cho mọi từ ngoài vocab SLAM.

Chọn sai biến thể là hỏng âm thầm (mọi mastery về prior mà không ai báo), nên
`/health` luôn nói rõ đang chạy biến thể nào.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

app = FastAPI(title="DKT Serve")

VARIANT = os.getenv("DKT_VARIANT", "feature").strip().lower()


def _server():
    """Nạp server theo biến thể đã chọn (mỗi loại tự cache singleton của nó)."""
    if VARIANT == "id":
        from src.serve import get_server

        return get_server()
    from src.serve_feat import get_server

    return get_server()


class PredictRequest(BaseModel):
    history: list[tuple[str, int]]   # [(token, correct)...] theo thứ tự thời gian
    targets: list[str]               # các từ cần ước lượng mastery
    #: Từ loại của từng từ nếu biết ("noun"/"NOUN"...). Chỉ biến thể feature dùng
    #: tới; thiếu vẫn chạy, chỉ mất một đặc trưng.
    pos: dict[str, str] = Field(default_factory=dict)
    #: Dạng bài của TỪNG lượt trong `history`, cùng thứ tự ("quiz", "typing"...).
    history_formats: list[str] = Field(default_factory=list)
    #: Dạng bài SẮP ra cho người học. Biết trước nên không phải thông tin tương lai.
    target_format: str | None = None


class PredictResponse(BaseModel):
    mastery: dict[str, float | None]  # None = không chấm được (caller áp prior)


@app.get("/health")
def health() -> dict:
    srv = _server()
    info: dict = {"status": "ok", "variant": VARIANT}
    if VARIANT == "id":
        info["vocab_size"] = srv.vocab
        info["note"] = "Bản theo ID: từ ngoài vocab SLAM sẽ trả None."
    else:
        info["feature_dim"] = srv.feature_dim
        info["use_history"] = srv.use_history
        info["note"] = "Bản feature-based: chấm được từ bất kỳ, không có vocab."
    return info


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    srv = _server()
    history = [(t, c) for t, c in req.history]
    if VARIANT == "id":
        mastery = srv.predict_mastery(history, req.targets)
    else:
        mastery = srv.predict_mastery(
            history, req.targets, pos=req.pos,
            history_formats=req.history_formats, target_format=req.target_format,
        )
    return PredictResponse(mastery=mastery)
