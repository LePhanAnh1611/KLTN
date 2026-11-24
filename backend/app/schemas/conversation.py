"""UC-39 — hội thoại roleplay với nhân vật AI."""
from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

#: Giới tính giọng đọc của nhân vật — frontend dùng để chọn giọng TTS khớp vai
#: (bug #11: Emma là nữ nhưng bị đọc bằng giọng nam).
VoiceGender = Literal["female", "male"]


class ScenarioDefinition(BaseModel):
    key: str
    name: str
    description: str
    persona: str
    voice: VoiceGender
    cefr: str
    #: Câu chào cố định — hiện được ở màn chọn kịch bản để người học biết trước
    #: mình sắp bước vào tình huống nào.
    opening: str


class ConversationTurnRow(BaseModel):
    ordinal: int
    speaker: str                    # 'ai' | 'user'
    text: str
    #: Gợi ý sửa câu. None = không có gì đáng sửa (khác chuỗi rỗng).
    correction: str | None
    asr_confidence: float | None
    created_at: datetime


class ConversationRow(BaseModel):
    id: int
    scenario: str
    scenario_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    turn_count: int


class ConversationDetail(BaseModel):
    id: int
    scenario: str
    scenario_name: str
    persona: str
    voice: VoiceGender
    cefr: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    turns: list[ConversationTurnRow]


class StartConversationRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=30)


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)
