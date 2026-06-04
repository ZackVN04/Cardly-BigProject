ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

# Redis key prefix for password-reset tokens issued after OTP verification.
# Full key: pwd_reset:{token_hex}  →  value: email address
RESET_TOKEN_PREFIX = "pwd_reset:"
