# TODO(P2 — Phúc Khang): Implement intake endpoints
# POST /documents   GET /documents   GET /documents/{id}/image   DELETE /documents/{id}
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def intake_ping() -> dict:
    return {"module": "intake", "status": "stub — not yet implemented"}
