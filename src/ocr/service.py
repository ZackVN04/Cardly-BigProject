"""
OCR service: PaddleOCR → Gemini LLM → normalize.

AC-8: removed blocking json.dumps(result) print from hot path.
AC-10: asyncio.wait_for wraps the Gemini call with a 10-second timeout.
Error handling: all raw exceptions mapped to typed AppException subclasses.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import cv2
import numpy as np
from google.genai.types import GenerateContentConfig

from .clients.gemini_client import get_gemini_client
from .clients.paddle_client import get_ocr_engine
from .constants import BusinessCardScanStatus
from .exceptions import (
    CardNotDetected,
    ExtractionTimeout,
    GeminiExtractionFailed,
    OcrSaveFailed,
)
from .models import BusinessCardScan
from .normalizer import normalize_gemini_response
from .response_schema import ExtractionResponse
from .schemas import BusinessCard

logger = logging.getLogger(__name__)

# AC-10: maximum allowed extraction time in seconds
_EXTRACTION_TIMEOUT_SECONDS = 10


async def save_ocr_raw_text(
    owner_id: str,
    processing_id: str,
    extracted_data: dict[str, Any],
    raw_text: str,
) -> BusinessCardScan:
    scan = BusinessCardScan(
        owner_id=owner_id,
        processing_id=processing_id,
        raw_text=raw_text,
        extracted_data=extracted_data,
        status=BusinessCardScanStatus.COMPLETED,
    )
    await scan.insert()
    return scan


async def pipline_ocr_to_llm(
    images_data: list[bytes],
    owner_id: str,
    processing_id: str,
) -> tuple[BusinessCardScan, ExtractionResponse]:
    """Run PaddleOCR → Gemini extraction → normalize, with timeout enforcement.

    AC-10: if the total time exceeds _EXTRACTION_TIMEOUT_SECONDS, raises
    ExtractionTimeout (HTTP 504) instead of propagating the raw asyncio error.
    """
    try:
        return await asyncio.wait_for(
            _run_extraction(images_data, owner_id, processing_id),
            timeout=_EXTRACTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Extraction timed out after %ds for processing_id=%s",
            _EXTRACTION_TIMEOUT_SECONDS,
            processing_id,
        )
        raise ExtractionTimeout()


async def _run_extraction(
    images_data: list[bytes],
    owner_id: str,
    processing_id: str,
) -> tuple[BusinessCardScan, ExtractionResponse]:
    """Inner extraction logic wrapped by the public timeout guard."""

    # ------------------------------------------------------------------
    # Step 1: PaddleOCR
    # ------------------------------------------------------------------
    ocr_engine = get_ocr_engine()
    raw_pages: list[Any] = []

    for image_data in images_data:
        img_np = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        raw_pages.append(ocr_engine.ocr(img_np))

    # Build flat text + block list for downstream use.
    # AC-8: removed the blocking json.dumps(raw_pages) print from the hot path.
    ocr_texts: list[str] = []
    ocr_blocks: list[dict[str, Any]] = []
    for page in raw_pages:
        if not page or page[0] is None:
            continue
        for block in page[0]:
            text: str = block[1][0]
            confidence: float = float(block[1][1])
            ocr_texts.append(text)
            ocr_blocks.append({"text": text, "confidence": confidence})

    ocr_text = "\n".join(ocr_texts)

    if not ocr_text.strip():
        raise CardNotDetected()

    # ------------------------------------------------------------------
    # Step 2: Persist raw OCR result
    # ------------------------------------------------------------------
    try:
        # BusinessCardScan.extracted_data is dict[str, Any]; wrap the list.
        scan = await save_ocr_raw_text(
            owner_id,
            processing_id,
            {"pages": raw_pages},
            ocr_text,
        )
    except Exception as exc:
        logger.error("Failed to save OCR result: %s", exc)
        raise OcrSaveFailed() from exc

    # ------------------------------------------------------------------
    # Step 3: Gemini LLM extraction
    # ------------------------------------------------------------------
    client = get_gemini_client()

    prompt = (
        "You are an AI expert in Document Information Extraction. "
        "Extract all fields from the business card text below. "
        "If a field is not present or cannot be read, omit it or set its value to null."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[prompt, ocr_text],
            config=GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BusinessCard.model_json_schema(),
                temperature=0.0,
            ),
        )
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise GeminiExtractionFailed() from exc

    # Parse JSON — strip markdown fences if present
    response_text = response.text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:-3]
    elif response_text.startswith("```"):
        response_text = response_text[3:-3]

    try:
        gemini_raw: dict[str, Any] = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned invalid JSON: %s", exc)
        raise GeminiExtractionFailed() from exc

    # ------------------------------------------------------------------
    # Step 4: Normalize into stable ExtractionResponse
    # ------------------------------------------------------------------
    normalized = normalize_gemini_response(gemini_raw, ocr_blocks, ocr_text)

    return scan, normalized
