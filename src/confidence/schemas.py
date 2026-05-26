from typing import Any

from pydantic import Field

from src.common.base_model import CustomModel


class FieldConfidenceSchema(CustomModel):
    field_name: str
    value: Any | None = None
    score: float
    classification: str
    validation_status: str = "passed"
    validation_errors: list[str] = Field(default_factory=list)
    auto_approved: bool
    requires_manual_review: bool
    note: str | None = None


class ConfidenceResponse(CustomModel):
    overall_score: float
    classification: str
    field_scores: list[FieldConfidenceSchema]
    failed_fields: list[str] = Field(default_factory=list)
    requires_manual_review: bool


class DocumentFullStateResponse(CustomModel):
    processing_id: str
    document_type: str | None = None
    status: str
    doc_type: str | None = None
    doc_type_confidence: float | None = None
    uploaded_at: str | None = None
    processed_at: str | None = None
    raw_ocr_output: Any | None = None
    normalized_fields: dict[str, Any] | None = None
    extracted_fields: dict[str, Any] | None = None
    validation_results: Any | None = None
    confidence_report: ConfidenceResponse | None = None
    confidence: ConfidenceResponse | None = None
    validation: dict[str, Any] | None = None
    processing_history: list[dict[str, Any]] = Field(default_factory=list)
