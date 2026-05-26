from datetime import datetime
from typing import Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType


class OcrBlock(BaseModel):
    """A single recognized text block from the OCR engine."""

    id: str | None = None
    text: str
    bbox: list[float] = Field(default_factory=list)
    confidence: float


class OcrResult(Document):
    """Raw OCR output kept verbatim for audit / re-review."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    preprocessed_image_id: PydanticObjectId
    ocr_engine: str
    raw_text: str
    blocks: list[OcrBlock] = []
    overall_confidence: float
    language_detected: str | None = None
    ocr_version: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ocr_results"


class VisionRegion(BaseModel):
    """A semantic region returned by the vision model."""

    label: str
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
