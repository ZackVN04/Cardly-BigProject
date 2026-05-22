# TODO(P1 — TBD): Implement auth endpoints
# POST /register  POST /login  POST /refresh  POST /logout  GET /me
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def auth_ping() -> dict:
    return {"module": "auth", "status": "stub — not yet implemented"}
