"""Request / response schemas for the auth module."""

from pydantic import EmailStr, Field, field_validator

from src.common.base_model import CustomModel


# ── Requests ──────────────────────────────────────────────────────────────────

class RegisterRequest(CustomModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class VerifyOtpRequest(CustomModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginRequest(CustomModel):
    email: EmailStr
    password: str


class RefreshRequest(CustomModel):
    refresh_token: str


class LogoutRequest(CustomModel):
    refresh_token: str


class ForgotPasswordRequest(CustomModel):
    email: EmailStr


class ResetPasswordRequest(CustomModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


# ── Responses ─────────────────────────────────────────────────────────────────

class TokenResponse(CustomModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(CustomModel):
    id: str
    email: str
    full_name: str
    is_active: bool


class MessageResponse(CustomModel):
    """Generic success response for operations that return no data."""
    success: bool = True
    message: str
