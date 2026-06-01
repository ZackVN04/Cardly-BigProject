# TODO(P4 — Cường Ngô + Thanh Thiệt): Implement Gemini Vision client
# Use GEMINI_API_KEY from ocr/config.py
import os
import functools
from google import genai
from src.ocr.config import ocr_settings

@functools.lru_cache(maxsize=1)
def get_gemini_client():
    return genai.Client(api_key=ocr_settings.GEMINI_API_KEY)
