# TODO(P7 — Khanh): Implement review endpoints
# PATCH /{processing_id}/review
# POST  /{processing_id}/confirm
# GET   /{processing_id}/final
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def review_ping() -> dict:
    return {"module": "review", "status": "stub — not yet implemented"}
