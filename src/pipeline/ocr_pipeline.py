"""
OCR pipeline orchestrator for the synchronous API endpoint.

This module wires together the GCS download, the preprocess adapter,
and the OCR service into a single callable used by ``src/ocr/router.py``.
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, status
from google.cloud import storage

from src.auth.models import User
from src.config import settings as global_cfg
from src.intake import config as intake_cfg
from src.ocr.models import BusinessCardScan
from src.ocr.response_schema import ExtractionResponse
from src.ocr.service import pipline_ocr_to_llm
from src.preprocess.adapter import preprocess_image_bytes

logger = logging.getLogger(__name__)


async def _download_images_from_gcs(processing_id: str) -> list[bytes]:
    """Fetch all non-rejected image blobs for *processing_id* from GCS."""
    from src.intake.models import ImageStatus, UploadedImage

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
        logger.info("Downloaded '%s' from GCS (%d bytes)", doc.storage_path, len(raw_bytes))
        images_raw.append(raw_bytes)

    return images_raw


async def run_ocr_pipeline(
    processing_id: str,
    user: User,
) -> tuple[BusinessCardScan, ExtractionResponse]:
    """Run the full preprocess -> OCR -> mapping/confidence pipeline."""
    logger.info("OCR pipeline started for processing_id='%s'", processing_id)

    images_raw: list[bytes] = await _download_images_from_gcs(processing_id)
    images_data: list[bytes] = await preprocess_image_bytes(images_raw)

    # Uncomment while diagnosing preprocess/OCR image quality issues.
    # _debug_dump_images(processing_id, images_raw, images_data)

    cardscan, normalized, ocr_blocks = await pipline_ocr_to_llm(
        images_data,
        str(user.id),
        processing_id,
    )

    await _run_mapping_and_confidence_stages(
        processing_id=processing_id,
        user_id=str(user.id),
        cardscan=cardscan,
        normalized=normalized,
        ocr_blocks=ocr_blocks,
    )
    logger.info("OCR pipeline completed for processing_id='%s'", processing_id)
    return cardscan, normalized


async def _run_mapping_and_confidence_stages(
    processing_id: str,
    user_id: str,
    cardscan: BusinessCardScan,
    normalized: ExtractionResponse,
    ocr_blocks: list[dict],
) -> None:
    """Persist P4 outputs, then run P5 mapping and P6 confidence scoring."""
    try:
        from beanie import PydanticObjectId

        from src.common.enums import DocType
        from src.confidence import service as confidence_service
        from src.intake.models import ImageStatus, UploadedImage
        from src.mapping import service as mapping_service
        from src.ocr.models import AiVisionResult, OcrBlock, OcrResult, VisionRegion
        from src.preprocess.models import PreprocessedImage

        prep = await PreprocessedImage.find_one(PreprocessedImage.processing_id == processing_id)
        prep_id = prep.id if prep else PydanticObjectId()

        ocr_res = await OcrResult.find_one(OcrResult.processing_id == processing_id)
        if ocr_res:
            await ocr_res.delete()

        blocks = [
            OcrBlock(
                id=block.get("id") or f"b_{index}",
                text=block["text"],
                bbox=block["bbox"],
                confidence=block["confidence"],
            )
            for index, block in enumerate(ocr_blocks)
        ]
        ocr_res = OcrResult(
            processing_id=processing_id,
            preprocessed_image_id=prep_id,
            ocr_engine="paddleocr",
            raw_text=cardscan.raw_text,
            blocks=blocks,
            overall_confidence=0.95,
            ocr_version="1.0",
        )
        await ocr_res.insert()

        extracted = normalized.model_dump(mode="python")
        label_to_result_keys: dict[str, list[str]] = {
            "name": ["name"],
            "phone": ["phones"],
            "email": ["email"],
            "web": ["website"],
            "position": ["position"],
            "company": ["company"],
            "address": ["address"],
        }

        def best_block_bbox(value: str | None) -> list[float]:
            if not value or not ocr_blocks:
                return [0.0, 0.0, 10.0, 10.0]
            needle = value.strip().lower()
            for block in ocr_blocks:
                if needle in block["text"].lower():
                    return block["bbox"]
            for block in ocr_blocks:
                if block["text"].lower() in needle:
                    return block["bbox"]
            return [0.0, 0.0, 10.0, 10.0]

        detected_regions: list[VisionRegion] = []
        for field_label, result_keys in label_to_result_keys.items():
            raw_value = extracted.get(result_keys[0])
            if isinstance(raw_value, list):
                raw_value = raw_value[0] if raw_value else None
            bbox = best_block_bbox(raw_value)
            detected_regions.append(VisionRegion(label=field_label, bbox=bbox, confidence=0.95))

        vision_res = await AiVisionResult.find_one(AiVisionResult.processing_id == processing_id)
        if vision_res:
            await vision_res.delete()

        vision_res = AiVisionResult(
            processing_id=processing_id,
            preprocessed_image_id=prep_id,
            doc_type=DocType.BUSINESS_CARD,
            doc_type_confidence=0.99,
            detected_regions=detected_regions,
            model_name="gemini",
            model_version="1.0",
        )
        await vision_res.insert()

        await mapping_service.map_document_fields(
            processing_id=processing_id,
            doc_type=DocType.BUSINESS_CARD,
            ocr_result=ocr_res.model_dump(),
            vision_result=vision_res.model_dump(),
            user_id=user_id,
        )

        await confidence_service.score_document(processing_id)

        await UploadedImage.find(UploadedImage.processing_id == processing_id).update(
            {"$set": {UploadedImage.status: ImageStatus.PROCESSED}}
        )
        logger.info(
            "UploadedImage status updated to 'processed' for processing_id='%s'",
            processing_id,
        )
    except Exception as exc:
        logger.error("Failed to run P5/P6 pipeline sync stages: %s", exc, exc_info=True)


_DEBUG_DIR = "storage/debug_ocr"


def _debug_dump_images(
    processing_id: str,
    images_raw: list[bytes],
    images_data: list[bytes],
) -> None:
    """Save raw and preprocessed image bytes for visual inspection."""
    os.makedirs(_DEBUG_DIR, exist_ok=True)

    def ext(data: bytes) -> str:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if data[:2] == b"\xff\xd8":
            return "jpg"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        return "bin"

    for index, (raw, processed) in enumerate(zip(images_raw, images_data, strict=False)):
        raw_path = os.path.join(_DEBUG_DIR, f"{processing_id}_{index}_raw.{ext(raw)}")
        proc_path = os.path.join(_DEBUG_DIR, f"{processing_id}_{index}_processed.{ext(processed)}")

        with open(raw_path, "wb") as file:
            file.write(raw)
        with open(proc_path, "wb") as file:
            file.write(processed)

        logger.info(
            "[DEBUG] Dumped image[%d] -> raw=%s (%d bytes), processed=%s (%d bytes)",
            index,
            raw_path,
            len(raw),
            proc_path,
            len(processed),
        )
