# TODO(P4 — Cường Ngô + Thanh Thiệt): Implement Tesseract OCR client
import functools
from paddleocr import PaddleOCR

@functools.lru_cache(maxsize=1)
def get_ocr_engine():
    return PaddleOCR(
        use_textline_orientation=True,
        lang='en',
    )

