from src.exceptions import AppException


class InvalidCredentials(AppException):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Invalid email or password"


class TokenExpired(AppException):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Token has expired"


class UserInactive(AppException):
    status_code = 403
    code = "FORBIDDEN"
    message = "User account is inactive"
