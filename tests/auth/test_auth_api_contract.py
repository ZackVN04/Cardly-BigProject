from typing import Any

import pytest

from src.auth import service

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_register_endpoint_calls_service_and_returns_contract_message(client, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_register_user(email: str, password: str, full_name: str) -> None:
        calls.append({"email": email, "password": password, "full_name": full_name})

    monkeypatch.setattr(service, "register_user", fake_register_user)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "Strong1!",
            "full_name": "Cardly User",
        },
    )

    assert response.status_code == 201
    assert calls == [
        {
            "email": "user@example.com",
            "password": "Strong1!",
            "full_name": "Cardly User",
        }
    ]
    assert response.json()["message"] == "Account created. Check your email for the verification OTP."


@pytest.mark.asyncio
async def test_register_endpoint_rejects_weak_password_before_service_call(client, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_register_user(email: str, password: str, full_name: str) -> None:
        calls.append({"email": email, "password": password, "full_name": full_name})

    monkeypatch.setattr(service, "register_user", fake_register_user)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "weakpass1!",
            "full_name": "Cardly User",
        },
    )

    assert response.status_code == 422
    assert calls == []


@pytest.mark.asyncio
async def test_verify_email_otp_endpoint_calls_service(client, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_verify_email_otp(email: str, otp: str) -> None:
        calls.append({"email": email, "otp": otp})

    monkeypatch.setattr(service, "verify_email_otp", fake_verify_email_otp)

    response = await client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": "user@example.com", "otp": "123456"},
    )

    assert response.status_code == 200
    assert calls == [{"email": "user@example.com", "otp": "123456"}]
    assert response.json()["message"] == "Email verified successfully."


@pytest.mark.asyncio
async def test_resend_verification_otp_endpoint_calls_service(client, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_resend_verification_otp(email: str) -> None:
        calls.append(email)

    monkeypatch.setattr(service, "resend_verification_otp", fake_resend_verification_otp)

    response = await client.post(
        "/api/v1/auth/resend-verification-otp",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 200
    assert calls == ["user@example.com"]
    assert "unverified" in response.json()["message"]


@pytest.mark.asyncio
async def test_forgot_password_endpoint_calls_service_and_uses_generic_message(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_send_password_reset_otp(email: str) -> None:
        calls.append(email)

    monkeypatch.setattr(service, "send_password_reset_otp", fake_send_password_reset_otp)

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 200
    assert calls == ["missing@example.com"]
    assert response.json()["message"] == "If that email is registered, you will receive a reset OTP shortly."


@pytest.mark.asyncio
async def test_reset_password_endpoint_calls_service_with_valid_schema(client, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_reset_password(email: str, otp: str, new_password: str) -> None:
        calls.append({"email": email, "otp": otp, "new_password": new_password})

    monkeypatch.setattr(service, "reset_password", fake_reset_password)

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "otp": "123456",
            "new_password": "NewPass1!",
            "confirm_password": "NewPass1!",
        },
    )

    assert response.status_code == 200
    assert calls == [
        {
            "email": "user@example.com",
            "otp": "123456",
            "new_password": "NewPass1!",
        }
    ]
    assert response.json()["message"] == "Password has been successfully reset."


@pytest.mark.asyncio
async def test_reset_password_endpoint_rejects_confirm_password_mismatch_before_service_call(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_reset_password(email: str, otp: str, new_password: str) -> None:
        calls.append({"email": email, "otp": otp, "new_password": new_password})

    monkeypatch.setattr(service, "reset_password", fake_reset_password)

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "user@example.com",
            "otp": "123456",
            "new_password": "NewPass1!",
            "confirm_password": "Different1!",
        },
    )

    assert response.status_code == 422
    assert calls == []
