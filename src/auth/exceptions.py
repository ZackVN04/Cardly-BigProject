from src.exceptions import AppException


# ── Registration ──────────────────────────────────────────────────────────────

class UserAlreadyExistsError(AppException):
    status_code = 409
    code = "USER_ALREADY_EXISTS"
    message = "An account with this email already exists."


# ── OTP ───────────────────────────────────────────────────────────────────────

class OtpExpiredError(AppException):
    status_code = 400
    code = "OTP_EXPIRED"
    message = "OTP has expired. Please request a new one."


class OtpInvalidError(AppException):
    status_code = 400
    code = "OTP_INVALID"
    message = "The OTP you entered is incorrect."


class OtpAlreadyUsedError(AppException):
    status_code = 400
    code = "OTP_ALREADY_USED"
    message = "This OTP has already been used."


# ── Authentication ────────────────────────────────────────────────────────────

class InvalidCredentialsError(AppException):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    message = "Invalid email or password."


class UserNotActiveError(AppException):
    status_code = 403
    code = "USER_NOT_ACTIVE"
    message = "Account is not yet verified. Please check your email for the OTP."


class UserAlreadyActiveError(AppException):
    status_code = 400
    code = "USER_ALREADY_ACTIVE"
    message = "Account is already active. Please log in."


class UserNotRegisteredError(AppException):
    status_code = 404
    code = "USER_NOT_REGISTERED"
    message = "This account is not registered"


# ── Tokens ────────────────────────────────────────────────────────────────────

class RefreshTokenInvalidError(AppException):
    status_code = 401
    code = "REFRESH_TOKEN_INVALID"
    message = "Refresh token is invalid, expired, or has been revoked."


class AccessTokenInvalidError(AppException):
    status_code = 401
    code = "ACCESS_TOKEN_INVALID"
    message = "Access token is invalid or expired."


class ResetTokenInvalidError(AppException):
    status_code = 400
    code = "RESET_TOKEN_INVALID"
    message = "Password reset token is invalid or has expired. Please request a new OTP."

class UserNotFound(AppException):
    status_code = 404
    code = "USER_NOT_FOUND"
    message = "No account found with that email address."