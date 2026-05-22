# TODO(P1 — TBD): Implement auth dependencies
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    # TODO: decode JWT, fetch User from DB, raise 401 if invalid
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Auth not implemented yet")
