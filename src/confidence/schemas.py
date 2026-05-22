# TODO(P6 — Nhân Tài): Implement confidence schemas
from src.common.base_model import CustomModel
from src.common.pagination import PaginatedResponse


class FieldConfidenceSchema(CustomModel):
    field_name: str
    score: float
    classification: str
    auto_approved: bool


class ConfidenceResponse(CustomModel):
    overall_score: float
    classification: str
    field_scores: list[FieldConfidenceSchema]
    requires_manual_review: bool


class DocumentFullStateResponse(CustomModel):
    processing_id: str
    status: str
    doc_type: str | None = None
    doc_type_confidence: float | None = None
    uploaded_at: str
    processed_at: str | None = None
    extracted_fields: dict | None = None
    confidence: ConfidenceResponse | None = None
    validation: dict | None = None
