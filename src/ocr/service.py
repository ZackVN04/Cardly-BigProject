
import io
import os
import json
from typing import Any

import cv2
import numpy as np
from google import genai
from PIL import Image
from google.genai.types import Tool, GenerateContentConfig

from .exceptions import CardNotDetected
from .schemas import BusinessCard
from .clients.paddle_client import get_ocr_engine
from .clients.gemini_client import get_gemini_client
from .models import BusinessCardScan
from .constants import BusinessCardScanStatus
from .normalizer import normalize_gemini_response
from .response_schema import ExtractionResponse

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
    extracted_data: [dict[str, Any]],
    raw_text: str,
) -> BusinessCardScan:
    scan = BusinessCardScan(
        owner_id=owner_id,
        processing_id=processing_id,
        raw_text=raw_text,
        extracted_data= extracted_data,
        status=BusinessCardScanStatus.COMPLETED,
    )
    await scan.insert()
    return scan


async def pipline_ocr_to_llm(
    images_data: list[bytes],
    owner_id: str,
    processing_id: str,
) -> tuple[BusinessCardScan, ExtractionResponse]:
    # Step 1: Run full OCR on the image
    ocr_engine = get_ocr_engine()
    result = []

    # Chạy OCR cho từng ảnh
    for image_data in images_data:
        img_np = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        result.append(ocr_engine.ocr(img_np))

    print("OCR Result: ", json.dumps(result, indent=4))

    # Chuẩn bị dữ liệu đầu vào cho LLM
    # Also build a flat list of OCR blocks for confidence resolution
    ocr_texts: list[str] = []
    ocr_blocks: list[dict[str, Any]] = []
    for page in result:
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
        raise CardNotDetected

    try:
        # BusinessCardScan.extracted_data requires a dict; wrap the PaddleOCR
        # list under a "pages" key so the raw output is still fully preserved.
        scan = await save_ocr_raw_text(owner_id, processing_id, {"pages": result}, ocr_text)
    except Exception as e:
        raise RuntimeError(f"Failed to save OCR result to DB: {e}") from e

    # Step 2: Send the extracted text to LLM
    client = get_gemini_client()
        
    prompt = f"""
        You are an AI expert in Document Information Extraction.
        If a field is not present or cannot be read, set value to null and confidence to 0.0.
        The confidence score should reflect how certain you are that the extracted value is correct based on the OCR text.
    """
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[prompt, ocr_text],
        config= GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BusinessCard.model_json_schema(),
            temperature=0.0
        )
    )
    
    # Parse the JSON response
    response_text = response.text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:-3]
    elif response_text.startswith("```"):
        response_text = response_text[3:-3]

    try:
        gemini_raw: dict[str, Any] = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}") from e

    # Step 3: Normalize the Gemini response into a stable, structured schema
    normalized = normalize_gemini_response(gemini_raw, ocr_blocks)

    return scan, normalized
