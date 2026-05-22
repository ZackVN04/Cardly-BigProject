from datetime import datetime
from typing import Any, Optional

from beanie import Document, Indexed
from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType


class OcrBlock(BaseModel):
    """A single recognized text block from the OCR engine."""

    text: str
    bbox: list[float]       # [x, y, w, h] in pixels
    confidence: float       # 0.0 – 1.0


class OcrResult(Document):
    """Raw OCR output kept verbatim for audit / re-review."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    preprocessed_image_id: PydanticObjectId
    ocr_engine: str
    raw_text: str
    blocks: list[OcrBlock] = []
    overall_confidence: float
    language_detected: Optional[str] = None
    ocr_version: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ocr_results"


class VisionRegion(BaseModel):
    """A semantic region returned by the vision model."""

    label: str              # e.g. "document_number", "surname", "mrz"
    bbox: list[float]
    confidence: float
    extra: dict[str, Any] = {}


class AiVisionResult(Document):
    """AI-Vision output: document classification + semantic regions."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    preprocessed_image_id: PydanticObjectId
    doc_type: DocType
    doc_type_confidence: float
    detected_regions: list[VisionRegion] = []
    model_name: str
    model_version: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ai_vision_results"
