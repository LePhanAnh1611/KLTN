"""UC-93 — đọc kết quả thí nghiệm so sánh lịch ôn (DKT vs SM-2).

Thí nghiệm chạy offline: `cd ml && python -m src.schedule_sim`. Nó ghi ra
`docs/experiments/scheduler_comparison.json` — file này ĐƯỢC commit, vì con số
trong chương thực nghiệm phải kiểm chứng lại được chứ không phải sinh ra lúc mở
màn hình.

Backend chỉ đọc và kiểm tra tính hợp lệ. Không tính lại: mô phỏng 60 ngày cho
120 người học mất vài phút và cần PyTorch — không thuộc về một request HTTP.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status

from app.schemas.scheduler_experiment import (
    SchedulerArm,
    SchedulerComparison,
    SchedulerGap,
    SchedulerSetup,
)

_FILENAME = "scheduler_comparison.json"
#: Trong container, docs/ được mount vào /app/docs (xem docker-compose.yml).
_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "docs" / "experiments" / _FILENAME

_RUN_HINT = (
    "Chưa có kết quả thí nghiệm. Chạy: cd ml && python -m src.schedule_sim "
    "(thêm --quick để thử nhanh)."
)


def result_path() -> Path:
    override = os.getenv("SCHEDULER_EXPERIMENT_PATH", "").strip()
    if override:
        return Path(override)
    docs_mount = Path("/app/docs/experiments") / _FILENAME
    if docs_mount.exists():
        return docs_mount
    return _DEFAULT_PATH


def _split_key(key: str) -> tuple[str, int, int]:
    """'dkt@b20p300' -> ('dkt', 20, 300)."""
    name, _, rest = key.partition("@")
    budget, _, pool = rest.lstrip("b").partition("p")
    return name, int(budget), int(pool)


def load(path: Path | None = None) -> SchedulerComparison:
    """Đọc file kết quả -> schema. 404 khi chưa chạy thí nghiệm, 500 khi file hỏng."""
    path = path or result_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, _RUN_HINT)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"File kết quả thí nghiệm không đọc được: {exc}",
        ) from exc

    try:
        arms = [
            SchedulerArm(scheduler=name, budget=budget, **{
                k: v for k, v in run.items() if k != "per_learner_delayed"
            })
            for key, run in raw["runs"].items()
            for name, budget, _pool in [_split_key(key)]
        ]
        gaps = [
            SchedulerGap(
                key=key, mean_diff=g["mean_diff"], ci_low=g["ci95"][0],
                ci_high=g["ci95"][1], win_rate=g["win_rate"],
                n_learners=g["n_learners"],
            )
            for key, g in raw["comparisons"].items()
        ]
        return SchedulerComparison(
            generated_at=raw["generated_at"],
            setup=SchedulerSetup(**raw["setup"]),
            memory_model=raw["memory_model"],
            # thứ tự ổn định: theo ngân sách rồi theo tên, để bảng không nhảy chỗ
            arms=sorted(arms, key=lambda a: (a.pool, a.budget, a.scheduler)),
            gaps=sorted(gaps, key=lambda g: g.key),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"File kết quả thí nghiệm sai định dạng: {exc}. {_RUN_HINT}",
        ) from exc


@lru_cache(maxsize=1)
def _cached(path_str: str, mtime: float) -> SchedulerComparison:
    return load(Path(path_str))


def get_comparison() -> SchedulerComparison:
    """Bản đã cache theo mtime — sửa file là lần gọi sau tự nạp lại."""
    path = result_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, _RUN_HINT)
    return _cached(str(path), path.stat().st_mtime)
