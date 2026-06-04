"""Repository — all MongoDB queries for the auth module.

Only raw DB operations live here.  No business logic, no error raising.
"""

from datetime import datetime

from beanie import PydanticObjectId

from src.auth.models import OtpCode, PasswordResetSession, RefreshToken, User


# ── User ──────────────────────────────────────────────────────────────────────

async def get_user_by_email(email: str) -> User | None:
    return await User.find_one(User.email == email)


async def get_user_by_id(user_id: PydanticObjectId) -> User | None:
    return await User.get(user_id)


async def create_user(email: str, password_hash: str, full_name: str) -> User:
    user = User(email=email, password_hash=password_hash, full_name=full_name)
    await user.insert()
    return user


async def activate_user(user: User) -> None:
    user.is_active = True
    user.updated_at = datetime.utcnow()
    await user.save()


async def update_password(user: User, new_password_hash: str) -> None:
    user.password_hash = new_password_hash
    user.updated_at = datetime.utcnow()
    await user.save()


# ── OTP ───────────────────────────────────────────────────────────────────────

async def create_otp(email: str, otp_hash: str, purpose: str, expires_at: datetime) -> OtpCode:
    otp_code = OtpCode(email=email, otp_hash=otp_hash, purpose=purpose, expires_at=expires_at)
    await otp_code.insert()
    return otp_code


async def get_latest_otp(email: str, purpose: str) -> OtpCode | None:
    """Return the most recently created, unused OTP for this email + purpose."""
    return await OtpCode.find_one(
        OtpCode.email == email,
        OtpCode.purpose == purpose,
        OtpCode.used == False,  # noqa: E712
        sort=[("created_at", -1)],
    )


async def mark_otp_used(otp_code: OtpCode) -> None:
    otp_code.used = True
    otp_code.updated_at = datetime.utcnow()
    await otp_code.save()


async def mark_otp_verified(otp_code: OtpCode) -> None:
    """Mark OTP as verified (used in the two-step reset flow) without fully consuming it."""
    otp_code.used = True
    otp_code.is_verified = True
    otp_code.updated_at = datetime.utcnow()
    await otp_code.save()


async def invalidate_old_otps(email: str, purpose: str) -> None:
    """Mark all previous unused OTPs for this email and purpose as used."""
    await OtpCode.find(
        OtpCode.email == email,
        OtpCode.purpose == purpose,
        OtpCode.used == False,  # noqa: E712
    ).update({"$set": {"used": True}})


# ── Refresh Token ─────────────────────────────────────────────────────────────

async def create_refresh_token(
    user_id: PydanticObjectId, token_hash: str, expires_at: datetime
) -> RefreshToken:
    token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    await token.insert()
    return token


async def get_refresh_token_by_hash(token_hash: str) -> RefreshToken | None:
    return await RefreshToken.find_one(RefreshToken.token_hash == token_hash)


async def revoke_refresh_token(token: RefreshToken) -> None:
    token.revoked = True
    await token.save()


async def revoke_all_refresh_tokens(user_id: PydanticObjectId) -> None:
    """Revoke every active refresh token for a user (used on password reset)."""
    await RefreshToken.find(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,  # noqa: E712
    ).update({"$set": {"revoked": True}})


# ── Password Reset Session ────────────────────────────────────────────────────

async def create_password_reset_session(
    user_id: PydanticObjectId, reset_token_hash: str, expires_at: datetime
) -> PasswordResetSession:
    session = PasswordResetSession(
        user_id=user_id,
        reset_token_hash=reset_token_hash,
        expires_at=expires_at,
    )
    await session.insert()
    return session


async def get_reset_session_by_token_hash(token_hash: str) -> PasswordResetSession | None:
    return await PasswordResetSession.find_one(PasswordResetSession.reset_token_hash == token_hash)


async def mark_reset_session_used(session: PasswordResetSession) -> None:
    session.is_used = True
    session.updated_at = datetime.utcnow()
    await session.save()


async def invalidate_old_reset_sessions(user_id: PydanticObjectId) -> None:
    """Mark all unused reset sessions for a user as used before issuing a new one."""
    await PasswordResetSession.find(
        PasswordResetSession.user_id == user_id,
        PasswordResetSession.is_used == False,  # noqa: E712
    ).update({"$set": {"is_used": True, "updated_at": datetime.utcnow()}})
