"""UC-12 — xóa tài khoản."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DeleteAccountRequest(BaseModel):
    """Yêu cầu mật khẩu hiện tại: đây là thao tác không hoàn tác được, không thể
    chỉ dựa vào việc trình duyệt đang giữ token."""

    password: str = Field(min_length=1)
    confirm: bool = Field(description="Phải là true — chống bấm nhầm")
