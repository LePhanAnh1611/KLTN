"""UC-44 — Thử thách hôm nay."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ChallengeItem(BaseModel):
    code: str
    title: str
    description: str
    target: int
    progress: int          # đã chặn trần ở target để thanh tiến độ không vượt 100%
    completed: bool
    claimed: bool
    xp_reward: int


class DailyChallenges(BaseModel):
    date: date
    items: list[ChallengeItem]
    claimable_count: int   # số thử thách đã xong mà chưa nhận thưởng
