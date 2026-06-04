"""
OCR service: PaddleOCR -> Gemini LLM -> normalize.

AC-8: avoid blocking debug prints in the extraction hot path.
AC-10: asyncio.wait_for wraps extraction with a 10-second timeout.
Error handling: raw failures are mapped to typed AppException subclasses.
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

_EXTRACTION_TIMEOUT_SECONDS = 10


def _polygon_to_bbox(polygon: list[Any]) -> list[float]:
    """Convert PaddleOCR polygon points to [x_min, y_min, width, height]."""
    xs = [float(p[0]) for p in polygon]
    ys = [float(p[1]) for p in polygon]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    return [x_min, y_min, x_max - x_min, y_max - y_min]


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
) -> tuple[BusinessCardScan, ExtractionResponse, list[dict[str, Any]]]:
    """Run PaddleOCR -> Gemini extraction -> normalized response.

    The OCR blocks are returned for the synchronous P5/P6 compatibility path,
    where real PaddleOCR bounding boxes are needed for field mapping.
    """
    try:
        return await asyncio.wait_for(
            _run_extraction(images_data, owner_id, processing_id),
            timeout=_EXTRACTION_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        logger.warning(
            "Extraction timed out after %ds for processing_id=%s",
            _EXTRACTION_TIMEOUT_SECONDS,
            processing_id,
        )
        raise ExtractionTimeout() from exc


async def _run_extraction(
    images_data: list[bytes],
    owner_id: str,
    processing_id: str,
) -> tuple[BusinessCardScan, ExtractionResponse, list[dict[str, Any]]]:
    ocr_engine = get_ocr_engine()
    raw_pages: list[Any] = []

    for image_data in images_data:
        img_np = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        raw_pages.append(ocr_engine.ocr(img_np))

    ocr_texts: list[str] = []
    ocr_blocks: list[dict[str, Any]] = []
    for page in raw_pages:
        if not page or page[0] is None:
            continue
        for block in page[0]:
            polygon, (text, confidence) = block[0], block[1]
            bbox = _polygon_to_bbox(polygon)
            ocr_texts.append(text)
            ocr_blocks.append(
                {
                    "id": f"b_{len(ocr_blocks)}",
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": bbox,
                }
            )

    ocr_text = "\n".join(ocr_texts)
    if not ocr_text.strip():
        raise CardNotDetected()

    try:
        scan = await save_ocr_raw_text(
            owner_id=owner_id,
            processing_id=processing_id,
            extracted_data={"pages": raw_pages},
            raw_text=ocr_text,
        )
    except Exception as exc:
        logger.error("Failed to save OCR result: %s", exc)
        raise OcrSaveFailed() from exc

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

    normalized = normalize_gemini_response(gemini_raw, ocr_blocks, ocr_text)
    return scan, normalized, ocr_blocks
