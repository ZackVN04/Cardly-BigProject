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

from fastapi import HTTPException, status
from google.cloud import storage

from src.auth.models import User
from src.ocr.models import BusinessCardScan
from src.intake import config as intake_cfg
from src.config import settings as global_cfg
from src.preprocess.adapter import preprocess_image_bytes
from src.ocr.service import pipline_ocr_to_llm

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


async def run_ocr_pipeline(processing_id: str, user: User) -> dict:
    """Run the full preprocess → OCR pipeline for an already-uploaded document.

    Parameters
    ----------
    processing_id:
        The correlation key assigned at upload time.  Used to locate and
        download all associated image files from GCS.

    Returns
    -------
    dict
        Structured OCR extraction result matching the ``BusinessCard`` schema.
    """
    logger.info("OCR pipeline started for processing_id='%s'", processing_id)

    # Step 1: download raw bytes from GCS
    images_raw: list[bytes] = await _download_images_from_gcs(processing_id)

    # Step 2: preprocess — list[bytes] → list[bytes] (processed)
    images_data: list[bytes] = await preprocess_image_bytes(images_raw)

    # Step 3: OCR + LLM extraction — list[bytes] → dict
    cardscan: BusinessCardScan
    result: dict

    cardscan, result = await pipline_ocr_to_llm(
        images_raw,
        str(user.id),
        processing_id
    )

    # Step 4: Synchronously run P5 mapping and P6 confidence scoring to support the local review/confirm API testing
    try:
        from src.ocr.models import OcrResult, OcrBlock, AiVisionResult, VisionRegion
        from src.common.enums import DocType
        from beanie import PydanticObjectId
        from src.preprocess.models import PreprocessedImage
        from src.mapping import service as mapping_service
        from src.confidence import service as confidence_service
        from src.intake.models import UploadedImage

        # Find preprocessed image
        prep = await PreprocessedImage.find_one(PreprocessedImage.processing_id == processing_id)
        prep_id = prep.id if prep else PydanticObjectId()

        # Save OcrResult (delete existing to overwrite schema)
        ocr_res = await OcrResult.find_one(OcrResult.processing_id == processing_id)
        if ocr_res:
            await ocr_res.delete()
        
        ocr_res = OcrResult(
            processing_id=processing_id,
            preprocessed_image_id=prep_id,
            ocr_engine="gemini",
            raw_text=cardscan.raw_text,
            blocks=[
                OcrBlock(id=f"b_{i}", text=line, bbox=[0.0, 0.0, 10.0, 10.0], confidence=0.95)
                for i, line in enumerate(cardscan.raw_text.split("\n"))
                if line.strip()
            ] if cardscan.raw_text else [],
            overall_confidence=0.95,
            ocr_version="1.0"
        )
        await ocr_res.insert()

        # Save AiVisionResult (delete existing to overwrite schema)
        vision_res = await AiVisionResult.find_one(AiVisionResult.processing_id == processing_id)
        if vision_res:
            await vision_res.delete()
            
        vision_res = AiVisionResult(
            processing_id=processing_id,
            preprocessed_image_id=prep_id,
            doc_type=DocType.BUSINESS_CARD,
            doc_type_confidence=0.99,
            detected_regions=[
                VisionRegion(label=field, bbox=[0, 0, 10, 10], confidence=0.95)
                for field in ["name", "phone", "email", "web", "position", "company"]
            ],
            model_name="gemini",
            model_version="1.0"
        )
        await vision_res.insert()

        # Map document fields (P5)
        await mapping_service.map_document_fields(
            processing_id=processing_id,
            doc_type=DocType.BUSINESS_CARD,
            ocr_result=ocr_res.model_dump(),
            vision_result=vision_res.model_dump(),
            user_id=str(user.id),
        )

        # Score document confidence (P6)
        await confidence_service.score_document(processing_id)

        # Update UploadedImage status to processed
        img = await UploadedImage.find_one(UploadedImage.processing_id == processing_id)
        if img:
            img.status = "processed"  # type: ignore[assignment]
            await img.save()
            logger.info("UploadedImage status updated to 'processed' for processing_id='%s'", processing_id)

    except Exception as e:
        logger.error("Failed to run P5/P6 pipeline sync stages: %s", str(e), exc_info=True)

    logger.info("OCR pipeline completed for processing_id='%s'", processing_id)
    return result
