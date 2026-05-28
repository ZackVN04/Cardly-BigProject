"""FastAPI dependency — resolve the current authenticated user from a Bearer token."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth import service
from src.auth.models import User
from src.auth.utils.jwt import decode_access_token

# HTTPBearer instructs Swagger UI to display a simple "Bearer token" input
# field instead of the OAuth2 Password Flow username/password form.
http_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> User:
    """Decode the Bearer token and return the corresponding active User.

    Raises AccessTokenInvalidError or UserNotActiveError (both mapped to
    HTTP 401/403 by the global exception handler).
    """
    user_id = decode_access_token(credentials.credentials)
    return await service.get_current_user(user_id)
