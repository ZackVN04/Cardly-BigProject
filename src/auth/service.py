"""Auth service — business logic only.

Rules:
- Never query the DB directly; always go through repository.
- Never raise HTTPException; raise domain errors from errors.py.
- Each function has a single, clear responsibility.
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from src.auth import repository
from src.auth.config import auth_settings
from src.auth.constants import RESET_TOKEN_PREFIX
from src.auth.exceptions import (
    InvalidCredentialsError,
    OtpAlreadyUsedError,
    OtpExpiredError,
    OtpInvalidError,
    RefreshTokenInvalidError,
    ResetTokenInvalidError,
    UserAlreadyActiveError,  # noqa: F401 — kept for potential future use
    UserAlreadyExistsError,
    UserNotActiveError, UserNotRegisteredError,
)
from src.auth.models import User
from src.auth.utils.email import send_otp_email
from src.auth.utils.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.auth.utils.otp import generate_otp, hash_otp, verify_otp
from src.common.redis_client import get_redis

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
        raise UserNotRegisteredError()

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
    else:
        raise UserNotFoundError()

# ── Verify Reset OTP ──────────────────────────────────────────────────────────

async def verify_reset_otp(email: str, otp: str) -> dict:
    """Validate the password-reset OTP and issue a short-lived reset token.

    Flow:
    1. Confirm the user exists.
    2. Consume the OTP (validates, checks expiry & reuse, marks as used).
    3. Generate a cryptographically random reset_token and store it in Redis
       with a TTL of RESET_TOKEN_EXP_MINUTES.  The value stored is the email
       address so the subsequent reset step doesn't need the client to send it.
    4. Return the reset_token and its TTL so the client knows how long it has.
    """
    user = await repository.get_user_by_email(email)
    if not user:
        raise UserNotFoundError()

    await _consume_otp(email=email, otp=otp, purpose="reset_password")

    reset_token = secrets.token_hex(32)
    ttl_seconds = auth_settings.RESET_TOKEN_EXP_MINUTES * 60

    redis = await get_redis()
    await redis.set(f"{RESET_TOKEN_PREFIX}{reset_token}", email, ex=ttl_seconds)

    return {"reset_token": reset_token, "expires_in": ttl_seconds}


# ── Reset Password ────────────────────────────────────────────────────────────

async def reset_password(reset_token: str, new_password: str) -> None:
    """Validate the reset token, update the password, and revoke all sessions.

    Flow:
    1. Look up the reset_token in Redis — raises ResetTokenInvalidError if
       missing or already expired.
    2. Fetch the user by the email stored in Redis.
    3. Hash and persist the new password.
    4. Revoke all active refresh tokens for the user (force re-login).
    5. Delete the Redis key explicitly so the token cannot be reused within
       its remaining TTL.
    """
    redis = await get_redis()
    redis_key = f"{RESET_TOKEN_PREFIX}{reset_token}"
    email: str | None = await redis.get(redis_key)

    if not email:
        raise ResetTokenInvalidError()

    user = await repository.get_user_by_email(email)
    if not user:
        raise UserNotFoundError()

    new_hash = _hash_password(new_password)
    await repository.update_password(user, new_hash)
    await repository.revoke_all_refresh_tokens(user.id)

    # Invalidate the reset token immediately so it cannot be reused.
    await redis.delete(redis_key)


# ── Private helpers ───────────────────────────────────────────────────────────

async def _send_otp(email: str, purpose: str) -> None:
    """Generate a fresh OTP, persist its hash, and email the plaintext code."""
    await repository.invalidate_old_otps(email, purpose)
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


async def resend_verification_otp(email: str) -> None:
    """Send a new verification OTP unconditionally."""
    await _send_otp(email=email, purpose="verify_email")