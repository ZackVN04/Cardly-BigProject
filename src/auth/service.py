"""Auth service — business logic only.

Rules:
- Never query the DB directly; always go through repository.
- Never raise HTTPException; raise domain errors from errors.py.
- Each function has a single, clear responsibility.
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt

from src.auth import repository
from src.auth.config import auth_settings
from src.auth.exceptions import (
    InvalidCredentialsError,
    OtpAlreadyUsedError,
    OtpExpiredError,
    OtpInvalidError,
    RefreshTokenInvalidError,
    UserAlreadyExistsError,
    UserNotActiveError,
    UserNotFoundError,
)
from src.auth.models import User
from src.auth.utils.email import send_otp_email
from src.auth.utils.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.auth.utils.otp import generate_otp, hash_otp, verify_otp

_BCRYPT_ROUNDS = 12


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prehash(plain: str) -> str:
    """SHA-256 → base64 the password before bcrypt.

    bcrypt silently truncates inputs longer than 72 bytes.  Pre-hashing
    reduces any password to a fixed 44-char ASCII string so bcrypt always
    receives the full entropy regardless of password length.
    """
    digest = hashlib.sha256(plain.encode()).digest()
    return base64.b64encode(digest).decode()


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prehash(plain).encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prehash(plain).encode(), hashed.encode())


def _hash_token(raw_token: str) -> str:
    """Store only a SHA-256 digest of the opaque refresh token value."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Registration ──────────────────────────────────────────────────────────────

async def register_user(email: str, password: str, full_name: str) -> None:
    """Create a new inactive user and send an email-verification OTP."""
    existing = await repository.get_user_by_email(email)
    if existing:
        raise UserAlreadyExistsError()

    password_hash = _hash_password(password)
    await repository.create_user(email=email, password_hash=password_hash, full_name=full_name)

    await _send_otp(email=email, purpose="verify_email")


# ── OTP Verification ──────────────────────────────────────────────────────────

async def verify_email_otp(email: str, otp: str) -> None:
    """Validate the OTP and activate the user account."""
    user = await repository.get_user_by_email(email)
    if not user:
        raise UserNotFoundError()

    await _consume_otp(email=email, otp=otp, purpose="verify_email")

    await repository.activate_user(user)


# ── Login ─────────────────────────────────────────────────────────────────────

async def login(email: str, password: str) -> dict:
    """Authenticate credentials and return a token pair."""
    user = await repository.get_user_by_email(email)
    if not user or not _check_password(password, user.password_hash):
        raise InvalidCredentialsError()

    if not user.is_active:
        raise UserNotActiveError()

    return await _issue_token_pair(str(user.id))


# ── Token Refresh ─────────────────────────────────────────────────────────────

async def refresh_access_token(raw_refresh_token: str) -> dict:
    """Validate the refresh token, revoke it, and issue a fresh pair."""
    user_id = decode_refresh_token(raw_refresh_token)   # raises on bad JWT
    token_hash = _hash_token(raw_refresh_token)

    stored = await repository.get_refresh_token_by_hash(token_hash)
    if not stored or stored.revoked or stored.expires_at.replace(tzinfo=timezone.utc) < _now_utc():
        raise RefreshTokenInvalidError()

    # Rotate: revoke old token and issue a new pair
    await repository.revoke_refresh_token(stored)
    return await _issue_token_pair(user_id)


# ── Logout ────────────────────────────────────────────────────────────────────

async def logout(raw_refresh_token: str) -> None:
    """Revoke the provided refresh token."""
    token_hash = _hash_token(raw_refresh_token)
    stored = await repository.get_refresh_token_by_hash(token_hash)
    if stored and not stored.revoked:
        await repository.revoke_refresh_token(stored)


# ── Forgot Password ───────────────────────────────────────────────────────────

async def send_password_reset_otp(email: str) -> None:
    """Send a password-reset OTP if the email belongs to an active account.

    Always returns without error even if the email is unknown — this
    prevents user enumeration attacks.
    """
    user = await repository.get_user_by_email(email)
    if user and user.is_active:
        await _send_otp(email=email, purpose="reset_password")


# ── Reset Password ────────────────────────────────────────────────────────────

async def reset_password(email: str, otp: str, new_password: str) -> None:
    """Validate OTP, update password hash, and revoke all existing sessions."""
    user = await repository.get_user_by_email(email)
    if not user:
        raise UserNotFoundError()

    await _consume_otp(email=email, otp=otp, purpose="reset_password")

    new_hash = _hash_password(new_password)
    await repository.update_password(user, new_hash)
    await repository.revoke_all_refresh_tokens(user.id)


# ── Private helpers ───────────────────────────────────────────────────────────

async def _send_otp(email: str, purpose: str) -> None:
    """Generate a fresh OTP, persist its hash, and email the plaintext code."""
    plain_otp = generate_otp()
    otp_hash = hash_otp(plain_otp)
    expires_at = _now_utc() + timedelta(minutes=auth_settings.OTP_EXP_MINUTES)

    await repository.create_otp(
        email=email,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=expires_at,
    )
    await send_otp_email(to_email=email, otp=plain_otp, purpose=purpose)


async def _consume_otp(email: str, otp: str, purpose: str) -> None:
    """Validate and mark an OTP as used.  Raises on any failure."""
    record = await repository.get_latest_otp(email=email, purpose=purpose)

    if not record:
        raise OtpInvalidError()

    if record.used:
        raise OtpAlreadyUsedError()

    if record.expires_at.replace(tzinfo=timezone.utc) < _now_utc():
        raise OtpExpiredError()

    if not verify_otp(otp, record.otp_hash):
        raise OtpInvalidError()

    await repository.mark_otp_used(record)


async def _issue_token_pair(user_id: str) -> dict:
    """Create an access + refresh token and persist the refresh token hash."""
    from beanie import PydanticObjectId

    access_token = create_access_token(user_id)
    raw_refresh = create_refresh_token(user_id)
    token_hash = _hash_token(raw_refresh)
    expires_at = _now_utc() + timedelta(days=auth_settings.REFRESH_TOKEN_EXP)

    await repository.create_refresh_token(
        user_id=PydanticObjectId(user_id),
        token_hash=token_hash,
        expires_at=expires_at,
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": auth_settings.JWT_EXP * 60,  # seconds
    }


async def get_current_user(user_id: str) -> User:
    """Fetch the full User document for an already-verified user_id."""
    from beanie import PydanticObjectId

    user = await repository.get_user_by_id(PydanticObjectId(user_id))
    if not user or not user.is_active:
        raise UserNotActiveError()
    return user
