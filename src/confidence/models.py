from datetime import datetime
from enum import Enum
from typing import Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType, ProcessingStage, StageStatus


class ConfidenceClass(str, Enum):
    HIGH = "high_confidence"
    LOW = "low_confidence"
    FAILED = "failed_confidence"


class OverallClassification(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class FieldConfidence(BaseModel):
    field_name: str
    value: Any | None = None
    score: float
    classification: ConfidenceClass
    validation_status: str = "passed"
    validation_errors: list[str] = Field(default_factory=list)
    auto_approved: bool = False
    requires_manual_review: bool = False
    note: str | None = None


class ConfidenceReport(Document):
    """Per-document confidence summary used to gate downstream workflows."""

    processing_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    mapped_document_id: PydanticObjectId
    document_type: DocType
    raw_ocr_output: dict[str, Any] | None = None
    normalized_fields: dict[str, Any] = Field(default_factory=dict)
    validation_results: Any = None
    field_scores: list[FieldConfidence]
    overall_score: float
    classification: OverallClassification
    flags: dict[str, bool] = Field(default_factory=dict)
    failed_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scored_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "confidence_reports"


class ProcessingHistory(Document):
    """Append-only audit log; one row per stage transition per processing_id."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    stage: ProcessingStage
    status: StageStatus
    details: dict[str, Any] = Field(default_factory=dict)
    ocr_version: str | None = None
    ai_model_version: str | None = None
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "processing_history"
