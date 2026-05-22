from datetime import datetime
from enum import Enum
from typing import Any, Optional

from beanie import Document, Indexed
from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType


class ReviewStatus(str, Enum):
    OPEN = "open"
    EDITING = "editing"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class EditOperation(BaseModel):
    field_name: str
    old_value: Any
    new_value: Any
    edited_at: datetime = Field(default_factory=datetime.utcnow)


class JsonReviewSession(Document):
    """A user-driven review/edit session over a MappedDocument."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    mapped_document_id: PydanticObjectId
    user_id: PydanticObjectId
    current_state: dict[str, Any]
    edit_log: list[EditOperation] = []
    validation_state: str = "pending"
    review_status: ReviewStatus = ReviewStatus.OPEN
    started_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None

    class Settings:
        name = "json_review_sessions"


class FinalizedDocument(Document):
    """Immutable final JSON after user confirmation."""

    processing_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    user_id: PydanticObjectId
    doc_type: DocType
    final_json: dict[str, Any]
    source_review_id: PydanticObjectId
    confirmed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "finalized_documents"
