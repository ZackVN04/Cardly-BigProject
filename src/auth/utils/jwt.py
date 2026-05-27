"""JWT helpers — create and verify access / refresh tokens."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from src.auth.config import auth_settings
from src.auth.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from src.auth.exceptions import AccessTokenInvalidError, RefreshTokenInvalidError


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: str) -> str:
    """Return a signed JWT that grants API access for JWT_EXP minutes."""
    payload = {
        "sub": user_id,
        "type": ACCESS_TOKEN_TYPE,
        "iat": _now_utc(),
        "exp": _now_utc() + timedelta(minutes=auth_settings.JWT_EXP),
    }
    return jwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALG)


def create_refresh_token(user_id: str) -> str:
    """Return a signed JWT used only to obtain new access tokens."""
    payload = {
        "sub": user_id,
        "type": REFRESH_TOKEN_TYPE,
        "iat": _now_utc(),
        "exp": _now_utc() + timedelta(days=auth_settings.REFRESH_TOKEN_EXP),
    }
    return jwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALG)


def decode_access_token(token: str) -> str:
    """Verify an access token and return the user_id it encodes.

    Raises AccessTokenInvalidError on any failure.
    """
    try:
        payload = jwt.decode(token, auth_settings.JWT_SECRET, algorithms=[auth_settings.JWT_ALG])
    except JWTError:
        raise AccessTokenInvalidError()

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise AccessTokenInvalidError()

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise AccessTokenInvalidError()

    return user_id


def decode_refresh_token(token: str) -> str:
    """Verify a refresh token and return the user_id it encodes.

    Raises RefreshTokenInvalidError on any failure.
    """
    try:
        payload = jwt.decode(token, auth_settings.JWT_SECRET, algorithms=[auth_settings.JWT_ALG])
    except JWTError:
        raise RefreshTokenInvalidError()

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise RefreshTokenInvalidError()

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise RefreshTokenInvalidError()

    return user_id
