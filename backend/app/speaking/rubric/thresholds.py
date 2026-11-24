"""Nạp `thresholds.json` — bản dịch rubric sang số cho C1/C2."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")


@lru_cache(maxsize=2)
def load_thresholds(path: str | None = None) -> dict:
    target = Path(path) if path else THRESHOLDS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def is_calibrated() -> bool:
    """Rubric mục 8: chưa đối chiếu với người chấm thật thì phải nói rõ."""
    return bool(load_thresholds().get("calibrated"))
