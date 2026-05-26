from fastapi import APIRouter

from src.confidence.schemas import DocumentFullStateResponse
from src.confidence.service import get_full_document_state

router = APIRouter()


@router.get("/ping")
async def confidence_ping() -> dict:
    return {"module": "confidence", "status": "ok"}


@router.get("/{processing_id}", response_model=DocumentFullStateResponse)
async def get_document(processing_id: str) -> DocumentFullStateResponse:
    """Return the full P6 document state for P7 review."""
    return await get_full_document_state(processing_id)
