import pytest
from pydantic import ValidationError

from src.auth.schemas import RegisterRequest, ResetPasswordRequest

pytestmark = pytest.mark.no_db


def test_register_accepts_strong_password() -> None:
    request = RegisterRequest(
        email="user@example.com",
        password="Strong1!",
        full_name="Cardly User",
    )

    assert request.password == "Strong1!"


@pytest.mark.parametrize(
    "password",
    [
        "short1!",
        "lowercase1!",
        "NO_DIGIT!",
        "NoSpecial1",
        "Has Space1!",
    ],
)
def test_register_rejects_weak_password(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password=password,
            full_name="Cardly User",
        )


@pytest.mark.parametrize(
    "password",
    [
        "short1!",
        "lowercase1!",
        "NO_DIGIT!",
        "NoSpecial1",
        "Has Space1!",
    ],
)
def test_reset_rejects_weak_password(password: str) -> None:
    with pytest.raises(ValidationError):
        ResetPasswordRequest(
            email="user@example.com",
            otp="123456",
            new_password=password,
            confirm_password=password,
        )


def test_reset_rejects_confirm_password_mismatch() -> None:
    with pytest.raises(ValidationError):
        ResetPasswordRequest(
            email="user@example.com",
            otp="123456",
            new_password="Strong1!",
            confirm_password="Different1!",
        )
