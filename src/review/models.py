from datetime import datetime
from enum import Enum
from typing import Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    EDITED = "edited"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ReviewField(BaseModel):
    field_name: str
    value: Any | None = None
    confidence_score: float | None = None
    validation_errors: list[str] = Field(default_factory=list)
    required: bool = False


class EditLog(BaseModel):
    field_name: str
    old_value: Any | None = None
    new_value: Any | None = None
    edited_by: str
    edited_at: datetime = Field(default_factory=datetime.utcnow)


class JsonReviewSession(Document):
    """Mutable review workspace for one processed document."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    mapped_document_id: PydanticObjectId | None = None
    user_id: PydanticObjectId | None = None
    raw_ocr_output: dict[str, Any] | str | None = None
    structured_data: dict[str, Any] = Field(default_factory=dict)
    confidence_scores: dict[str, Any] = Field(default_factory=dict)
    validation_status: dict[str, Any] = Field(default_factory=dict)
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    edit_logs: list[EditLog] = Field(default_factory=list)
    final_data: dict[str, Any] | None = None
    is_locked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: datetime | None = None

    class Settings:
        name = "json_review_sessions"


class FinalizedDocument(Document):
    """Immutable final JSON after user confirmation."""

    processing_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    user_id: PydanticObjectId | None = None
    doc_type: DocType = DocType.BUSINESS_CARD
    final_data: dict[str, Any]
    final_json: dict[str, Any]
    source_review_id: PydanticObjectId
    confirmed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "finalized_documents"


class ReviewResponse(BaseModel):
    processing_id: str
    raw_ocr_output: dict[str, Any] | str | None = None
    structured_data: dict[str, Any]
    confidence_scores: dict[str, Any]
    validation_status: dict[str, Any]
    review_status: ReviewStatus
    edit_logs: list[EditLog]
    final_data: dict[str, Any] | None = None
    is_locked: bool
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None


class ReviewUpdateRequest(BaseModel):
    updates: dict[str, Any]


class ReviewUpdateResponse(ReviewResponse):
    pass


class ConfirmResponse(BaseModel):
    processing_id: str
    review_status: ReviewStatus
    final_data: dict[str, Any]
    confirmed_at: datetime
    is_locked: bool
