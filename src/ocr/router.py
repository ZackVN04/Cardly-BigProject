"""OCR router — route definitions only.

Responsibilities:
  1. Accept a ``processing_id`` path parameter identifying an already-uploaded document.
  2. Delegate orchestration to ``src.pipeline.ocr_pipeline.run_ocr_pipeline``,
     which downloads images from GCS and runs the preprocess → OCR pipeline.
  3. Return a structured HTTP response.

No business logic lives here.  All domain errors bubble up from the service
layers and are caught by the global AppException handler registered in main.py.

Authentication: this endpoint is public — no token required.
"""

from fastapi import APIRouter, status
from fastapi.params import Depends

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.pipeline.ocr_pipeline import run_ocr_pipeline
from .schemas import ExtractionResponse

router = APIRouter()


@router.post(
    "/pipeline/{processing_id}",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the full preprocess → OCR pipeline on an already-uploaded document",
)
async def ocr_pipeline(
    processing_id: str,
    user: User = Depends(get_current_user),
) -> ExtractionResponse:
    """Download the image(s) for *processing_id* from GCS, preprocess them,
    run OCR extraction, and return the normalized structured result.

    - **processing_id**: the correlation key returned by the upload endpoint
      (`POST /api/v1/documents`).  One or two images may be associated with
      this ID (front and back of a card).

    Returns an ``ExtractionResponse`` with all contact fields, confidence
    values, and extraction status — missing values are null/[] rather than
    being omitted.

    Raises **404** if no documents are found for the given ``processing_id``.
    Raises **502** if a GCS download fails.
    """
    _scan, normalized = await run_ocr_pipeline(processing_id, user)
    return normalized
