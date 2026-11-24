"""UC-03 xác thực email · UC-06 quên/đặt lại mật khẩu."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Mật khẩu mới theo đúng luật của đăng ký (E2 UC-06)."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def password_must_have_letter_and_digit(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("new_password and new_password_confirm do not match")
        return self


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class VerifyEmailResponse(BaseModel):
    email: str
    already_verified: bool


class MessageResponse(BaseModel):
    """Phản hồi trung tính — không tiết lộ email có tồn tại hay không (UC-06 1a)."""

    message: str
