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


async def run_ocr_pipeline(processing_id: str) -> dict:
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
    result: dict = await pipline_ocr_to_llm(images_raw)

    logger.info("OCR pipeline completed for processing_id='%s'", processing_id)
    return result
