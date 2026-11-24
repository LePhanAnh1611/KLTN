from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AchievementStatus(BaseModel):
    code: str
    name: str
    description: str
    unlocked: bool
    unlocked_at: datetime | None = None
