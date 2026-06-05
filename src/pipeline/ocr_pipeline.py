"""
OCR pipeline orchestrator for the synchronous API endpoint.

This module wires together the GCS download, the preprocess adapter,
and the OCR service into a single callable used by ``src/ocr/router.py``.

Flow
----
  1. Look up all ``UploadedImage`` records for the given ``processing_id``
     (there may be 1 or 2, representing front/back of a card).
  2. Download each image's bytes directly from Google Cloud Storage.
  3. Pass the raw bytes list through the preprocess adapter,
     which returns ``images_data: list[bytes]``.
  4. Pass ``images_data`` to ``src.ocr.service.pipline_ocr_to_llm``.
  5. Return the resulting dict to the router.

This module contains **no business logic** — it only orchestrates existing
modules and must not duplicate logic from ``src/preprocess``, ``src/ocr``,
or ``src/intake``.
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, status
from google.cloud import storage

from src.auth.models import User
from src.ocr.models import BusinessCardScan
from src.ocr.schemas import ExtractionResponse
from src.intake import config as intake_cfg
from src.config import settings as global_cfg
from src.preprocess.adapter import preprocess_image_bytes
from src.ocr.service import pipline_ocr_to_llm
from src.ocr.constants import BusinessCardScanStatus
from src.mapping.normalizers import normalize_fields
from src.common.enums import DocType
from src.confidence.service import build_field_scores, calculate_overall_score

logger = logging.getLogger(__name__)

async def _download_images_from_gcs(processing_id: str) -> list[bytes]:
    """Fetch all image blobs for *processing_id* from GCS and return their bytes.

    Looks up every ``UploadedImage`` document associated with *processing_id*
    (1 or 2 files) and downloads each one directly from Cloud Storage.

    Raises
    ------
    HTTPException 404
        If no documents are found for the given ``processing_id``.
    HTTPException 502
        If a GCS download fails.
    """
    from src.intake.models import UploadedImage, ImageStatus
    docs = await UploadedImage.find(
        UploadedImage.processing_id == processing_id,
        UploadedImage.status != ImageStatus.REJECTED_INVALID,
    ).to_list()

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No documents found for processing_id '{processing_id}'",
        )

    if global_cfg.gcs_credentials:
        client = storage.Client(credentials=global_cfg.gcs_credentials)
    else:
        client = storage.Client()

    bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)
    images_raw: list[bytes] = []

    for doc in docs:
        blob = bucket.blob(doc.storage_path)
        if not blob.exists():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Image file not found in storage: '{doc.storage_path}'",
            )
        raw_bytes: bytes = blob.download_as_bytes()
        logger.info(
            "Downloaded '%s' from GCS (%d bytes)",
            doc.storage_path,
            len(raw_bytes),
        )
        images_raw.append(raw_bytes)

    return images_raw


async def run_ocr_pipeline(processing_id: str, user: User) -> tuple[BusinessCardScan, ExtractionResponse]:
    """Run the full preprocess → OCR pipeline for an already-uploaded document.

    Parameters
    ----------
    processing_id:
        The correlation key assigned at upload time.  Used to locate and
        download all associated image files from GCS.

    Returns
    -------
    tuple[BusinessCardScan, ExtractionResponse]
        The persisted scan record and the fully-normalized extraction result.
    """
    logger.info("OCR pipeline started for processing_id='%s'", processing_id)

    # Step 1: download raw bytes from GCS
    images_raw: list[bytes] = await _download_images_from_gcs(processing_id)

    # Step 2: preprocess — list[bytes] → list[bytes] (processed)
    images_data: list[bytes] = await preprocess_image_bytes(images_raw)

    # ------------------------------------------------------------------
    # DEBUG: dump raw vs preprocessed images for visual inspection.
    # Remove this block once the preprocessing issue is resolved.
    # ------------------------------------------------------------------
    # _debug_dump_images(processing_id, images_raw, images_data)
    # ------------------------------------------------------------------

    # Step 3: OCR + LLM extraction
    cardscan: BusinessCardScan
    
    cardscan, raw_extracted_dict, ocr_blocks = await pipline_ocr_to_llm(
        images_raw,
        str(user.id),
        processing_id
    )

    # Step 4: Clean up extracted data
    cleaned_dict = normalize_fields(DocType.BUSINESS_CARD, raw_extracted_dict)
    
    # Step 5: Score the extracted data
    field_scores = build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields=cleaned_dict,
        validation_results=[],
        ocr_blocks=ocr_blocks
    )
    overall_score = calculate_overall_score(DocType.BUSINESS_CARD, field_scores)
    
    # Step 6: Wrap in response schema
    extraction_response = ExtractionResponse(
        **cleaned_dict,
        confidence_score=overall_score,
        field_scores=[score.model_dump() for score in field_scores]
    )
    
    # Step 7: Save the result to MongoDB and update status
    cardscan.extracted_data = extraction_response.model_dump()
    cardscan.status = BusinessCardScanStatus.COMPLETED
    await cardscan.save()
    
    # Step 8: Update the status of the associated UploadedImage documents
    from src.intake.models import UploadedImage, ImageStatus
    await UploadedImage.find(
        UploadedImage.processing_id == processing_id
    ).update({"$set": {UploadedImage.status: ImageStatus.PROCESSED}})
    
    logger.info("OCR pipeline completed for processing_id='%s'", processing_id)
    return cardscan, extraction_response

# ---------------------------------------------------------------------------
# DEBUG helper — remove once preprocessing issue is diagnosed
# ---------------------------------------------------------------------------

_DEBUG_DIR = "storage/debug_ocr"

def _debug_dump_images(
    processing_id: str,
    images_raw: list[bytes],
    images_data: list[bytes],
) -> None:
    """Save raw and preprocessed image bytes to *_DEBUG_DIR* for visual inspection.

    Each call writes two files per image index::

        storage/debug_ocr/<processing_id>_<idx>_raw.<ext>
        storage/debug_ocr/<processing_id>_<idx>_processed.<ext>

    The extension is inferred from the leading magic bytes so the files open
    correctly in any image viewer.
    """
    os.makedirs(_DEBUG_DIR, exist_ok=True)

    def _ext(data: bytes) -> str:
        """Guess file extension from magic bytes."""
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if data[:2] == b"\xff\xd8":
            return "jpg"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        return "bin"

    for idx, (raw, processed) in enumerate(zip(images_raw, images_data)):
        raw_path = os.path.join(_DEBUG_DIR, f"{processing_id}_{idx}_raw.{_ext(raw)}")
        proc_path = os.path.join(_DEBUG_DIR, f"{processing_id}_{idx}_processed.{_ext(processed)}")

        with open(raw_path, "wb") as f:
            f.write(raw)
        with open(proc_path, "wb") as f:
            f.write(processed)

        logger.info(
            "[DEBUG] Dumped image[%d] → raw=%s (%d bytes)  processed=%s (%d bytes)",
            idx, raw_path, len(raw), proc_path, len(processed),
        )
