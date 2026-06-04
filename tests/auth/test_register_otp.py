from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from beanie import PydanticObjectId

from src.auth import service
from src.auth.constants import OTP_PURPOSE_RESET_PASSWORD, OTP_PURPOSE_VERIFY_EMAIL
from src.auth.exceptions import OtpInvalidError, PasswordReuseError, UserNotActiveError
from src.auth.utils.otp import hash_otp

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_register_creates_active_unverified_user_and_sends_verify_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}
    otp_purposes: list[str] = []

    async def fake_get_user_by_email(email: str) -> None:
        return None

    async def fake_create_user(email: str, password_hash: str, full_name: str) -> SimpleNamespace:
        created.update(email=email, password_hash=password_hash, full_name=full_name)
        return SimpleNamespace(
            id=PydanticObjectId(),
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            is_active=True,
            email_verified=False,
        )

    async def fake_invalidate_old_otps(email: str, purpose: str) -> None:
        otp_purposes.append(purpose)

    async def fake_create_otp(email: str, otp_hash: str, purpose: str, expires_at: datetime) -> None:
        otp_purposes.append(purpose)

    async def fake_send_otp_email(to_email: str, otp: str, purpose: str) -> None:
        otp_purposes.append(purpose)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service.repository, "create_user", fake_create_user)
    monkeypatch.setattr(service.repository, "invalidate_old_otps", fake_invalidate_old_otps)
    monkeypatch.setattr(service.repository, "create_otp", fake_create_otp)
    monkeypatch.setattr(service, "send_otp_email", fake_send_otp_email)

    await service.register_user("user@example.com", "Strong1!", "Cardly User")

    assert created["email"] == "user@example.com"
    assert created["full_name"] == "Cardly User"
    assert all(purpose == OTP_PURPOSE_VERIFY_EMAIL for purpose in otp_purposes)


@pytest.mark.asyncio
async def test_verify_email_otp_consumes_only_verify_email_purpose(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(email_verified=False)
    otp_record = SimpleNamespace(id="otp-1")
    validated: dict[str, str] = {}
    activated: list[SimpleNamespace] = []
    marked_used: list[SimpleNamespace] = []

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_validate_otp(email: str, otp: str, purpose: str) -> SimpleNamespace:
        validated.update(email=email, otp=otp, purpose=purpose)
        return otp_record

    async def fake_activate_user(user_arg: SimpleNamespace) -> None:
        activated.append(user_arg)

    async def fake_mark_otp_used(record: SimpleNamespace) -> None:
        marked_used.append(record)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_validate_otp", fake_validate_otp)
    monkeypatch.setattr(service.repository, "activate_user", fake_activate_user)
    monkeypatch.setattr(service.repository, "mark_otp_used", fake_mark_otp_used)

    await service.verify_email_otp("user@example.com", "123456")

    assert validated == {
        "email": "user@example.com",
        "otp": "123456",
        "purpose": OTP_PURPOSE_VERIFY_EMAIL,
    }
    assert activated == [user]
    assert marked_used == [otp_record]


@pytest.mark.asyncio
async def test_verify_email_does_not_consume_otp_when_activation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(email_verified=False)
    otp_record = SimpleNamespace(id="otp-1")
    marked_used: list[SimpleNamespace] = []

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_validate_otp(email: str, otp: str, purpose: str) -> SimpleNamespace:
        return otp_record

    async def fake_activate_user(user_arg: SimpleNamespace) -> None:
        raise RuntimeError("db failure")

    async def fake_mark_otp_used(record: SimpleNamespace) -> None:
        marked_used.append(record)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_validate_otp", fake_validate_otp)
    monkeypatch.setattr(service.repository, "activate_user", fake_activate_user)
    monkeypatch.setattr(service.repository, "mark_otp_used", fake_mark_otp_used)

    with pytest.raises(RuntimeError):
        await service.verify_email_otp("user@example.com", "123456")

    assert marked_used == []


@pytest.mark.asyncio
async def test_verify_email_otp_rejects_reset_password_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(email_verified=False)

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_get_latest_otp(email: str, purpose: str) -> None:
        assert purpose == OTP_PURPOSE_VERIFY_EMAIL
        return None

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service.repository, "get_latest_otp", fake_get_latest_otp)

    with pytest.raises(OtpInvalidError):
        await service.verify_email_otp("user@example.com", "123456")


@pytest.mark.asyncio
async def test_forgot_password_sends_reset_password_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(is_active=True)
    purposes: list[str] = []

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_send_otp(email: str, purpose: str) -> None:
        purposes.append(purpose)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_send_otp", fake_send_otp)

    await service.send_password_reset_otp("user@example.com")

    assert purposes == [OTP_PURPOSE_RESET_PASSWORD]


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_does_not_send_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    purposes: list[str] = []

    async def fake_get_user_by_email(email: str) -> None:
        return None

    async def fake_send_otp(email: str, purpose: str) -> None:
        purposes.append(purpose)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_send_otp", fake_send_otp)

    await service.send_password_reset_otp("missing@example.com")

    assert purposes == []


@pytest.mark.asyncio
async def test_resend_verification_otp_sends_new_verify_email_otp_for_unverified_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(email_verified=False)
    purposes: list[str] = []

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_send_otp(email: str, purpose: str) -> None:
        purposes.append(purpose)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_send_otp", fake_send_otp)

    await service.resend_verification_otp("user@example.com")

    assert purposes == [OTP_PURPOSE_VERIFY_EMAIL]


@pytest.mark.asyncio
async def test_send_otp_invalidates_old_otp_creates_new_expiry_and_sends_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalidated: list[tuple[str, str]] = []
    created: list[dict[str, Any]] = []
    sent: list[tuple[str, str]] = []

    async def fake_invalidate_old_otps(email: str, purpose: str) -> None:
        invalidated.append((email, purpose))

    async def fake_create_otp(email: str, otp_hash: str, purpose: str, expires_at: datetime) -> None:
        created.append(
            {
                "email": email,
                "otp_hash": otp_hash,
                "purpose": purpose,
                "expires_at": expires_at,
            }
        )

    async def fake_send_otp_email(to_email: str, otp: str, purpose: str) -> None:
        sent.append((to_email, purpose))

    monkeypatch.setattr(service.repository, "invalidate_old_otps", fake_invalidate_old_otps)
    monkeypatch.setattr(service.repository, "create_otp", fake_create_otp)
    monkeypatch.setattr(service, "send_otp_email", fake_send_otp_email)

    before = service._now_utc()
    await service._send_otp("user@example.com", OTP_PURPOSE_VERIFY_EMAIL)
    after = service._now_utc()

    assert invalidated == [("user@example.com", OTP_PURPOSE_VERIFY_EMAIL)]
    assert len(created) == 1
    assert created[0]["email"] == "user@example.com"
    assert created[0]["purpose"] == OTP_PURPOSE_VERIFY_EMAIL
    assert created[0]["otp_hash"]
    assert before + timedelta(minutes=service.auth_settings.OTP_EXP_MINUTES) <= created[0]["expires_at"]
    assert created[0]["expires_at"] <= after + timedelta(minutes=service.auth_settings.OTP_EXP_MINUTES)
    assert sent == [("user@example.com", OTP_PURPOSE_VERIFY_EMAIL)]


@pytest.mark.asyncio
async def test_reset_password_consumes_only_reset_password_purpose_and_revokes_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(
        id=PydanticObjectId(),
        password_hash=service._hash_password("OldPass1!"),
    )
    otp_record = SimpleNamespace(id="otp-1")
    validated: dict[str, str] = {}
    updated_hashes: list[str] = []
    revoked_user_ids: list[PydanticObjectId] = []
    marked_used: list[SimpleNamespace] = []

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_validate_otp(email: str, otp: str, purpose: str) -> SimpleNamespace:
        validated.update(email=email, otp=otp, purpose=purpose)
        return otp_record

    async def fake_update_password(user_arg: SimpleNamespace, new_password_hash: str) -> None:
        updated_hashes.append(new_password_hash)

    async def fake_revoke_all_refresh_tokens(user_id: PydanticObjectId) -> None:
        revoked_user_ids.append(user_id)

    async def fake_mark_otp_used(record: SimpleNamespace) -> None:
        marked_used.append(record)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_validate_otp", fake_validate_otp)
    monkeypatch.setattr(service.repository, "update_password", fake_update_password)
    monkeypatch.setattr(service.repository, "revoke_all_refresh_tokens", fake_revoke_all_refresh_tokens)
    monkeypatch.setattr(service.repository, "mark_otp_used", fake_mark_otp_used)

    await service.reset_password("user@example.com", "123456", "NewPass1!")

    assert validated == {
        "email": "user@example.com",
        "otp": "123456",
        "purpose": OTP_PURPOSE_RESET_PASSWORD,
    }
    assert len(updated_hashes) == 1
    assert revoked_user_ids == [user.id]
    assert marked_used == [otp_record]


@pytest.mark.asyncio
async def test_reset_password_does_not_consume_otp_when_update_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=PydanticObjectId(),
        password_hash=service._hash_password("OldPass1!"),
    )
    otp_record = SimpleNamespace(id="otp-1")
    marked_used: list[SimpleNamespace] = []

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_validate_otp(email: str, otp: str, purpose: str) -> SimpleNamespace:
        return otp_record

    async def fake_update_password(user_arg: SimpleNamespace, new_password_hash: str) -> None:
        raise RuntimeError("db failure")

    async def fake_mark_otp_used(record: SimpleNamespace) -> None:
        marked_used.append(record)

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_validate_otp", fake_validate_otp)
    monkeypatch.setattr(service.repository, "update_password", fake_update_password)
    monkeypatch.setattr(service.repository, "mark_otp_used", fake_mark_otp_used)

    with pytest.raises(RuntimeError):
        await service.reset_password("user@example.com", "123456", "NewPass1!")

    assert marked_used == []


@pytest.mark.asyncio
async def test_reset_password_rejects_verify_email_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=PydanticObjectId(),
        password_hash=service._hash_password("OldPass1!"),
    )

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_get_latest_otp(email: str, purpose: str) -> None:
        assert purpose == OTP_PURPOSE_RESET_PASSWORD
        return None

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service.repository, "get_latest_otp", fake_get_latest_otp)

    with pytest.raises(OtpInvalidError):
        await service.reset_password("user@example.com", "123456", "NewPass1!")


@pytest.mark.asyncio
async def test_reset_password_rejects_reused_password(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=PydanticObjectId(),
        password_hash=service._hash_password("OldPass1!"),
    )

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)

    with pytest.raises(PasswordReuseError):
        await service.reset_password("user@example.com", "123456", "OldPass1!")


@pytest.mark.asyncio
async def test_unverified_active_user_can_login(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=PydanticObjectId(),
        password_hash=service._hash_password("Strong1!"),
        is_active=True,
        email_verified=False,
    )

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    async def fake_issue_token_pair(user_id: str) -> dict[str, Any]:
        return {
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "bearer",
            "expires_in": 900,
        }

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "_issue_token_pair", fake_issue_token_pair)

    tokens = await service.login("user@example.com", "Strong1!")

    assert tokens["access_token"] == "access"


@pytest.mark.asyncio
async def test_inactive_user_cannot_login(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=PydanticObjectId(),
        password_hash=service._hash_password("Strong1!"),
        is_active=False,
        email_verified=True,
    )

    async def fake_get_user_by_email(email: str) -> SimpleNamespace:
        return user

    monkeypatch.setattr(service.repository, "get_user_by_email", fake_get_user_by_email)

    with pytest.raises(UserNotActiveError):
        await service.login("user@example.com", "Strong1!")


@pytest.mark.asyncio
async def test_consume_otp_rejects_expired_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    record = SimpleNamespace(
        used=False,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        otp_hash=hash_otp("123456"),
    )

    async def fake_get_latest_otp(email: str, purpose: str) -> SimpleNamespace:
        return record

    monkeypatch.setattr(service.repository, "get_latest_otp", fake_get_latest_otp)

    with pytest.raises(service.OtpExpiredError):
        await service._consume_otp("user@example.com", "123456", OTP_PURPOSE_VERIFY_EMAIL)
