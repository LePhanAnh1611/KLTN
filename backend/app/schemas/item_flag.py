"""UC-32 — đánh dấu từ khó."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FlagRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class FlaggedItem(BaseModel):
    item_id: int
    word: str
    meaning: str
    word_set_id: int
    word_set_name: str
    note: str | None
    # None = chưa từng học từ này, nên chưa có mastery để đối chiếu
    mastery: float | None
    flagged_at: datetime


class FlagResponse(BaseModel):
    model_config = {"from_attributes": True}

    item_id: int
    note: str | None
