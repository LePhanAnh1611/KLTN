"""UC-97 — Shadowing theo phụ đề video YouTube."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.pronunciation import AspectOut, WordCheckOut

License = Literal["public-domain", "cc-by", "cc-by-sa", "youtube-standard"]


class SegmentOut(BaseModel):
    index: int
    start: float
    end: float
    text: str
    words_per_minute: float | None = None


class SegmentProgress(BaseModel):
    index: int
    attempts: int
    best_accuracy: float | None
    passed: bool


class ShadowingVideoCard(BaseModel):
    """Một ô trong lưới video — không kèm phụ đề cho nhẹ."""

    id: int
    youtube_id: str
    title: str
    channel: str | None
    topic: str | None
    cefr_level: str | None
    words_per_minute: float | None
    duration_sec: float | None
    segment_count: int
    source: Literal["catalog", "user"]
    license: str | None
    attribution: str | None
    passed_count: int = 0


class ShadowingVideoDetail(ShadowingVideoCard):
    caption_kind: str
    segments: list[SegmentOut]
    vocab_profile: dict | None
    progress: list[SegmentProgress]
    pass_accuracy: float


class ShadowingTopics(BaseModel):
    topics: list[str]
    levels: list[str]
    licenses: list[str]


class ShadowingAttemptResult(BaseModel):
    attempt_id: int
    video_id: int
    segment_index: int
    expected_text: str
    transcript: str
    accuracy: float
    clarity: float
    overall_level: int
    aspects: list[AspectOut]
    words: list[WordCheckOut]
    missed_words: list[str]
    extra_words: list[str]
    audio_metrics: dict
    feedback: str
    warnings: list[str]
    # Riêng của shadowing: bắt nhịp người nói gốc
    learner_wpm: float | None
    original_wpm: float | None
    speed_ratio: float | None
    speed_feedback: str | None
    passed: bool
    pass_accuracy: float


# ------------------------------------------------------------------ Admin

class ShadowingAdminRow(ShadowingVideoCard):
    status: Literal["draft", "published"]
    caption_kind: str
    created_at: datetime
    published_at: datetime | None


class ShadowingAdminDetail(ShadowingAdminRow):
    segments: list[SegmentOut]
    vocab_profile: dict | None


class SegmentEdit(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=1000)


class ShadowingVideoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    topic: str | None = None
    license: License | None = None
    attribution: str | None = Field(default=None, max_length=1000)
    segments: list[SegmentEdit] | None = None


class ShadowingStatusUpdate(BaseModel):
    status: Literal["draft", "published"]
