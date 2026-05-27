from datetime import datetime

from beanie import Document, Indexed, PydanticObjectId
from pydantic import EmailStr, Field


class User(Document):
    """Application user — stores credentials and activation state."""

    email: Indexed(EmailStr, unique=True)  # type: ignore[valid-type]
    password_hash: str
    full_name: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"


class RefreshToken(Document):
    """Hashed refresh token stored per session.  Revoked on logout / password reset."""

    user_id: PydanticObjectId
    token_hash: Indexed(str, unique=True)  # type: ignore[valid-type]
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "refresh_tokens"


class OtpCode(Document):
    """Hashed one-time-password for email verification and password reset."""

    email: Indexed(EmailStr)  # type: ignore[valid-type]
    otp_hash: str
    purpose: str          # "verify_email" | "reset_password"
    expires_at: datetime
    used: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "otp_codes"
