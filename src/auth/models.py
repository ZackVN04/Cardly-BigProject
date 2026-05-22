from datetime import datetime
from enum import Enum

from beanie import Document, Indexed
from pydantic import EmailStr, Field
from beanie import PydanticObjectId


class UserRole(str, Enum):
    USER = "user"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class User(Document):
    """Application user (uploader / reviewer / admin)."""

    email: Indexed(EmailStr, unique=True)  # type: ignore[valid-type]
    password_hash: str
    full_name: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"


class RefreshToken(Document):
    """Hashed refresh tokens for JWT rotation."""

    user_id: PydanticObjectId
    token_hash: Indexed(str, unique=True)  # type: ignore[valid-type]
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "refresh_tokens"
