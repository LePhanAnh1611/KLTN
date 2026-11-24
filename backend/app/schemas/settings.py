"""UC-07 đổi mật khẩu · UC-09 cài đặt · UC-10 đặt mục tiêu học."""
from __future__ import annotations

from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.clock import is_valid_timezone

UiLanguage = Literal["vi", "en"]
ProfileVisibility = Literal["public", "private"]
CefrTarget = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

# UC-10 luồng thay thế 1a — giá trị mặc định nay nằm ở bảng cấu hình (UC-81),
# đọc qua gamification_service.default_daily_item_goal().


class ChangePasswordRequest(BaseModel):
    """UC-07 — cùng luật mật khẩu với đăng ký (>=8 ký tự, có chữ và số)."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def password_must_have_letter_and_digit(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("new_password and new_password_confirm do not match")
        return self


class SettingsResponse(BaseModel):
    """Toàn bộ USER_SETTINGS người học chỉnh được (UC-09 + UC-10)."""

    model_config = {"from_attributes": True}

    # UC-09
    dark_mode: bool
    ui_language: str
    reminder_time: time | None
    timezone: str                      # UC-88 — quyết định "hôm nay" là ngày nào
    profile_visibility: str
    # UC-10
    daily_item_goal: int | None
    daily_xp_goal: int | None
    target_cefr_level: str | None
    # UC-11: do bài kiểm tra ước lượng, nhưng người học tự chỉnh được (UC-10)
    entry_cefr_level: str | None


class SettingsUpdate(BaseModel):
    """UC-09 — gửi field nào thì đổi field đó (bỏ trống = giữ nguyên)."""

    dark_mode: bool | None = None
    ui_language: UiLanguage | None = None
    reminder_time: time | None = None
    timezone: str | None = Field(default=None, max_length=64)
    profile_visibility: ProfileVisibility | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_iana(cls, value: str | None) -> str | None:
        """Chặn tên múi giờ bịa ngay ở biên: sai múi giờ là sai luôn streak,
        mục tiêu ngày và thử thách của người học."""
        if value is not None and not is_valid_timezone(value):
            raise ValueError("Múi giờ không hợp lệ (cần tên dạng IANA, VD Asia/Ho_Chi_Minh)")
        return value


class GoalsUpdate(BaseModel):
    """UC-10 — E1: giá trị ngoài khoảng an toàn bị chặn ngay ở schema."""

    daily_item_goal: int | None = Field(default=None, ge=1, le=200)
    daily_xp_goal: int | None = Field(default=None, ge=10, le=1000)
    target_cefr_level: CefrTarget | None = None
    # Người học thấy mức hệ thống ước lượng quá dễ/quá khó thì chỉnh thẳng ở đây,
    # không phải làm lại cả bài kiểm tra. Đổi mức là lộ trình (UC-84) sinh lại.
    entry_cefr_level: CefrTarget | None = None
