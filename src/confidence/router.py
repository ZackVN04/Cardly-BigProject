import logging

from fastapi import APIRouter

from src.confidence.exceptions import DocumentNotFound
from src.confidence.schemas import DocumentFullStateResponse
from src.confidence.service import get_full_document_state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ping")
async def confidence_ping() -> dict:
    return {"module": "confidence", "status": "ok"}


@router.get("/{processing_id}", response_model=DocumentFullStateResponse)
async def get_document(processing_id: str) -> DocumentFullStateResponse:
    """Return the full P6 document state for P7 review."""
    try:
        return await get_full_document_state(processing_id)
    except DocumentNotFound:
        logger.error(
            "Confidence retrieval failed: processing_id=%s unavailable",
            processing_id,
        )
        raise
