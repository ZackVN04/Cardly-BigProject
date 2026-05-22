from datetime import datetime
from enum import Enum
from typing import Any, Optional

from beanie import Document, Indexed
from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType, ProcessingStage, StageStatus


class ConfidenceClass(str, Enum):
    HIGH = "high"     # >= 0.95
    LOW = "low"       # 0.70 – 0.95
    FAILED = "failed" # < 0.70


class FieldConfidence(BaseModel):
    field_name: str
    score: float
    classification: ConfidenceClass
    auto_approved: bool = False
    note: Optional[str] = None


class ConfidenceReport(Document):
    """Per-document confidence summary used to gate downstream workflows."""

    processing_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    mapped_document_id: PydanticObjectId
    field_scores: list[FieldConfidence]
    overall_score: float
    classification: ConfidenceClass
    flags: dict[str, bool] = {}
    failed_fields: list[str] = []
    scored_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "confidence_reports"


class ProcessingHistory(Document):
    """Append-only audit log; one row per stage transition per processing_id."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    stage: ProcessingStage
    status: StageStatus
    details: dict[str, Any] = {}
    ocr_version: Optional[str] = None
    ai_model_version: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "processing_history"
