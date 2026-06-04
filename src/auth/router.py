"""Auth router — route definitions only.

Responsibilities:
  1. Parse and validate the request body (via Pydantic schemas).
  2. Call the service layer.
  3. Return a structured HTTP response.

No business logic lives here.  All domain errors bubble up from the service
and are caught by the global AppException handler registered in main.py.
"""

from fastapi import APIRouter, Depends, status

from src.auth import service
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
    VerifyResetOtpRequest,
    VerifyResetOtpResponse,
)

router = APIRouter()


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    summary="Register a new account",
)
async def register(body: RegisterRequest) -> MessageResponse:
    await service.register_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    return MessageResponse(message="Account created. Check your email for the verification OTP.")


@router.post(
    "/verify-otp",
    response_model=MessageResponse,
    summary="Verify email with OTP",
)
async def verify_otp(body: VerifyOtpRequest) -> MessageResponse:
    await service.verify_email_otp(email=body.email, otp=body.otp)
    return MessageResponse(message="Email verified. Your account is now active.")


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive token pair",
)
async def login(body: LoginRequest) -> TokenResponse:
    tokens = await service.login(
        email=body.email,
        password=body.password,
    )
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(body: RefreshRequest) -> TokenResponse:
    tokens = await service.refresh_access_token(body.refresh_token)
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the current refresh token",
)
async def logout(body: LogoutRequest) -> MessageResponse:
    await service.logout(body.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password-reset OTP",
)
async def forgot_password(body: ForgotPasswordRequest) -> MessageResponse:
    await service.send_password_reset_otp(email=body.email)
    # Always return the same message to avoid leaking whether the email exists.
    return MessageResponse(
        message="If that email is registered, you will receive a reset OTP shortly."
    )


@router.post(
    "/verify-reset-otp",
    response_model=VerifyResetOtpResponse,
    summary="Verify the password-reset OTP and receive a reset token",
)
async def verify_reset_otp(body: VerifyResetOtpRequest) -> VerifyResetOtpResponse:
    """Step 1 of the two-step password-reset flow.

    Validates the OTP emailed by POST /forgot-password and, on success,
    returns a short-lived reset_token that must be presented to
    POST /reset-password.
    """
    result = await service.verify_reset_otp(email=body.email, otp=body.otp)
    return VerifyResetOtpResponse(**result)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a verified reset token",
)
async def reset_password(body: ResetPasswordRequest) -> MessageResponse:
    """Step 2 of the two-step password-reset flow.

    Requires the reset_token issued by POST /verify-reset-otp.
    The token is single-use and expires after RESET_TOKEN_EXP_MINUTES.
    """
    await service.reset_password(
        reset_token=body.reset_token,
        new_password=body.new_password,
    )
    return MessageResponse(message="Password updated successfully. Please log in again.")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
    )


@router.post(
    "/resend-otp",
    response_model=MessageResponse,
    summary="Resend verification OTP",
)
async def resend_otp(body: ResendOtpRequest) -> MessageResponse:
    await service.resend_verification_otp(email=body.email)
    return MessageResponse(message="If that email is registered and inactive, a new OTP has been sent.")
