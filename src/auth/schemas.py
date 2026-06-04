"""Request / response schemas for the auth module."""

from pydantic import EmailStr, Field, field_validator, model_validator

from src.auth.constants import PASSWORD_SPECIAL_CHARACTERS
from src.common.base_model import CustomModel


def validate_password_policy(value: str) -> str:
    """Validate the Cardly password policy shared by register and reset flows."""
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if any(character.isspace() for character in value):
        raise ValueError("Password must not contain spaces.")
    if not any(character.isupper() for character in value):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(character.isdigit() for character in value):
        raise ValueError("Password must contain at least one digit.")
    if not any(character in PASSWORD_SPECIAL_CHARACTERS for character in value):
        raise ValueError("Password must contain at least one special character.")
    return value


# ── Requests ──────────────────────────────────────────────────────────────────

class RegisterRequest(CustomModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_policy(v)


class VerifyOtpRequest(CustomModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendOtpRequest(CustomModel):
    email: EmailStr


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
    confirm_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_policy(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Confirm password must match new password.")
        return self


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
    email_verified: bool = False


class MessageResponse(CustomModel):
    """Generic success response for operations that return no data."""
    success: bool = True
    message: str
