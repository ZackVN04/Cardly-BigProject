# TODO(P6 — Nhân Tài): Implement GET /documents and GET /documents/{processing_id}
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def confidence_ping() -> dict:
    return {"module": "confidence", "status": "stub — not yet implemented"}
