"""Client gọi service DKT (UC-68) qua HTTP nội bộ.

Degrade mềm (UC-64 E2): nếu service lỗi/timeout, trả None cho mọi target để
caller dùng cold-start/prior thay vì chặn luồng học.

Để việc "degrade mềm" thật sự MỀM, có hai lớp bảo vệ:
- tách connect timeout (ngắn) khỏi read timeout: khi ml-serve tắt, trên Windows
  kết nối tới 127.0.0.1 không bị từ chối ngay mà treo ở SYN_SENT tới hết timeout;
- ngắt mạch (circuit breaker): sau khi lỗi, tạm ngừng gọi trong ít giây thay vì
  mỗi câu trả lời lại trả giá timeout một lần.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# connect ngắn vì ml-serve luôn ở cùng máy/mạng nội bộ; read dài hơn cho suy luận
_TIMEOUT = httpx.Timeout(connect=1.0, read=5.0, write=5.0, pool=1.0)

# Một client dùng chung cho cả tiến trình. `httpx.post()` tạo client mới mỗi lần
# gọi — nạp lại chứng chỉ SSL và mở kết nối TCP mới, ~0,35 giây trên Windows,
# trong khi bản thân việc chấm 400 từ chỉ mất ~0,03 giây. Giữ kết nối sống thì
# chỉ trả phí đó một lần.
_http = httpx.Client(timeout=_TIMEOUT)

COOLDOWN_SECONDS = 30.0  # sau khi lỗi thì nghỉ bấy nhiêu giây rồi mới thử lại

_disabled_until: float = 0.0


def reset_circuit() -> None:
    """Cho phép gọi lại ngay (dùng trong test)."""
    global _disabled_until
    _disabled_until = 0.0


def _all_unknown(targets: list[str]) -> dict[str, float | None]:
    return {t: None for t in targets}


def predict_mastery(
    history: list[tuple[str, int]],
    targets: list[str],
    pos: dict[str, str] | None = None,
    history_formats: list[str] | None = None,
    target_format: str | None = None,
) -> dict[str, float | None]:
    """history: [(word, correct)...] theo thời gian; targets: list word.
    Trả {word: P(correct) hoặc None}. None = cold-start / service không sẵn sàng.

    `pos` là từ loại của từng từ nếu biết. Bản DKT feature-based dùng nó làm một
    chiều đặc trưng — đo thử thì thiếu từ loại làm lệch dự đoán đáng kể (0.72 so
    với 0.84 trên cùng một từ). Bản theo ID bỏ qua trường này.

    `history_formats`/`target_format` là DẠNG BÀI (quiz/typing/dictation...).
    Không gửi thì mô hình nhận mã "other" — một giá trị nó gần như chưa từng thấy
    lúc huấn luyện, nên dự đoán sẽ kém đi. Đây là lệch train/serve rất dễ mắc:
    API vẫn 200, số vẫn có, chỉ là tệ hơn mà không ai biết.
    """
    global _disabled_until

    if not targets:
        return {}

    # Đang trong thời gian ngắt mạch -> trả ngay, không tốn timeout
    if time.monotonic() < _disabled_until:
        return _all_unknown(targets)

    try:
        resp = _http.post(
            f"{settings.ml_serve_url}/predict",
            json={
                "history": history, "targets": targets, "pos": pos or {},
                "history_formats": history_formats or [],
                "target_format": target_format,
            },
        )
        resp.raise_for_status()
        mastery = resp.json()["mastery"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        _disabled_until = time.monotonic() + COOLDOWN_SECONDS
        logger.warning(
            "Service DKT không phản hồi (%s) — dùng cold-start prior, tạm ngừng gọi %.0fs",
            exc.__class__.__name__, COOLDOWN_SECONDS,
        )
        return _all_unknown(targets)

    _disabled_until = 0.0
    return mastery
