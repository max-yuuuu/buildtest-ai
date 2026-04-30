import re

from pydantic import BaseModel, EmailStr, field_validator


class SendCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = "register"

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        if v not in ("register",):
            raise ValueError("invalid purpose")
        return v


class SendCodeResponse(BaseModel):
    success: bool
    expires_in: int = 300


class RegisterRequest(BaseModel):
    email: EmailStr
    code: str
    password: str
    name: str | None = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("验证码必须为 6 位数字")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度不能少于 8 位")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"\d", v):
            raise ValueError("密码必须包含字母和数字")
        return v


class RegisterResponse(BaseModel):
    success: bool


class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckEmailResponse(BaseModel):
    registered: bool


class VerifyPasswordRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyPasswordResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
