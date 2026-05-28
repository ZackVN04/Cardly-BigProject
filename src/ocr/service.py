
import io
import os
import json

import cv2
import numpy as np
from google import genai
from PIL import Image
from google.genai.types import Tool, GenerateContentConfig
from .schemas import BusinessCard
from .clients.paddle_client import get_ocr_engine
from .clients.gemini_client import get_gemini_client
from .models import BusinessCardScan
from .constants import BusinessCardScanStatus

async def save_ocr_raw_text(
    owner_id: str,
    processing_id: str,
    raw_text: str,
) -> BusinessCardScan:
    scan = BusinessCardScan(
        owner_id=owner_id,
        processing_id=processing_id,
        raw_text=raw_text,
        status=BusinessCardScanStatus.PROCESSING,
    )
    await scan.insert()
    return scan


async def pipline_ocr_to_llm(images_data: list[bytes], owner_id: str, processing_id: str) -> tuple[BusinessCardScan, dict]:
    # Step 1: Run full OCR on the image
    ocr_engine = get_ocr_engine()
    result = []

    # Chạy OCR cho từng ảnh
    for image_data in images_data:
        img_np = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        result.append(ocr_engine.ocr(img_np))

    print("OCR Result: ", json.dumps(result, indent=4))

    # Chuẩn bị dữ liệu đầu vào cho LLM
    ocr_texts = []
    for page in result:
        if not page or page[0] is None:
            continue
        for block in page[0]:
            ocr_texts.append(block[1][0])
    ocr_text = "\n".join(ocr_texts)

    if not ocr_text.strip():
        raise RuntimeError("OCR extracted no text from the provided images")

    try:
        scan = await save_ocr_raw_text(owner_id, processing_id, ocr_text)
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
        return scan, json.loads(response_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}") from e
