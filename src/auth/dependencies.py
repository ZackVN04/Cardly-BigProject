"""FastAPI dependency — resolve the current authenticated user from a Bearer token."""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.auth import service
from src.auth.models import User
from src.auth.utils.jwt import decode_access_token

# tokenUrl must match the full mounted path of the login endpoint so that
# Swagger UI's "Authorize" button knows where to POST credentials.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Decode the Bearer token and return the corresponding active User.

    Raises AccessTokenInvalidError or UserNotActiveError (both mapped to
    HTTP 401/403 by the global exception handler).
    """
    user_id = decode_access_token(token)
    return await service.get_current_user(user_id)
