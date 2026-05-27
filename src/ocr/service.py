
import io
import os
import json
import numpy as np
from google import genai
from PIL import Image
from google.genai.types import Tool, GenerateContentConfig
from .schemas import BusinessCard
from .clients.paddle_client import get_ocr_engine
from .clients.gemini_client import get_gemini_client

async def pipline_ocr_to_llm(images_data: list[bytes]):
    # Step 1: Run full OCR on the image
    ocr_engine = get_ocr_engine()
    result = []

    # Chạy OCR cho từng ảnh
    for image_data in images_data:
        img = Image.open(io.BytesIO(image_data)).convert('RGB')
        img_np = np.array(img)
        result.append(ocr_engine.ocr(img_np))

    print("OCR Result: ", json.dumps(result, indent=4))

    # Chuẩn bị dữ liệu đầu vào cho LLM
    ocr_texts = []
    for page in result:
        for block in page[0]:
            ocr_texts.append(block[1][0])
    ocr_text = "\n".join(ocr_texts)

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
        
    return json.loads(response_text)