"""UC-24 (bộ từ) & UC-53 (bài viết) — báo cáo vi phạm."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ReportReason = Literal["wrong_content", "spam", "copyright", "offensive", "other"]


class ReportRequest(BaseModel):
    reason: ReportReason
    description: str | None = Field(default=None, max_length=1000)


class ReportResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    target_type: str
    target_id: int
    reason: str
    description: str | None
    status: str
    created_at: datetime
    merged: bool = False  # E1: trùng báo cáo cũ đang chờ xử lý -> gộp, không tạo mới
