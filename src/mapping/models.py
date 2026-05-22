from datetime import datetime
from enum import Enum
from typing import Any

from beanie import Document, Indexed
from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from src.common.enums import DocType


class MappingStatus(str, Enum):
    PENDING = "pending"
    MAPPED = "mapped"
    PARTIAL = "partial"
    FAILED = "failed"


class FieldValidationResult(BaseModel):
    field_name: str
    rule: str
    passed: bool
    message: str | None = None


class MappedDocument(Document):
    """Structured business data mapped from OCR + Vision results.

    `extracted_fields` holds the raw mapping (1:1 with OCR text).
    `normalized_fields` holds canonical values (ISO dates, trimmed strings, etc.).
    Fields that cannot be extracted are stored as null — keys are never dropped.
    """

    processing_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    doc_type: DocType
    user_id: PydanticObjectId
    extracted_fields: dict[str, Any]
    normalized_fields: dict[str, Any]
    validation_results: list[FieldValidationResult] = []
    missing_required_fields: list[str] = []
    mapping_status: MappingStatus = MappingStatus.PENDING
    mapper_version: str
    mapped_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "mapped_documents"
