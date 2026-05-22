# TODO(P1 — TBD): Implement auth schemas
from src.common.base_model import CustomModel


class RegisterRequest(CustomModel):
    email: str
    password: str
    full_name: str


class LoginRequest(CustomModel):
    email: str
    password: str


class TokenResponse(CustomModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(CustomModel):
    refresh_token: str


class UserResponse(CustomModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
