# =============================================================
# OCR Document Processing System - MongoDB Schemas
# Stack: FastAPI + Beanie ODM (async MongoDB) + Pydantic v2
# =============================================================
# Comments in English to keep codebase consistent.
# Each Collection below maps to a Beanie Document class.
# =============================================================

from datetime import datetime, date
from enum import Enum
from typing import Optional, Any
from beanie import Document, Indexed, Link, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field


# =============================================================
# ENUMS (shared across collections)
# =============================================================

class UserRole(str, Enum):
    USER = "user"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class DocType(str, Enum):
    PASSPORT_AU = "passport_au"
    MEDICARE = "medicare"
    DRIVER_LICENCE_VIC = "driver_licence_vic"
    UNKNOWN = "unknown"


class ImageStatus(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    REJECTED_INVALID = "rejected_invalid"
    REJECTED_DUPLICATE = "rejected_duplicate"
    PREPROCESSING = "preprocessing"
    PROCESSED = "processed"
    FAILED = "failed"


class PreprocessingStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class MappingStatus(str, Enum):
    PENDING = "pending"
    MAPPED = "mapped"
    PARTIAL = "partial"
    FAILED = "failed"


class ConfidenceClass(str, Enum):
    HIGH = "high"          # >= 95%
    LOW = "low"            # 70% - 95%
    FAILED = "failed"      # < 70%


class ProcessingStage(str, Enum):
    INTAKE = "intake"
    PREPROCESS = "preprocess"
    OCR = "ocr"
    AI_VISION = "ai_vision"
    FIELD_MAPPING = "field_mapping"
    CONFIDENCE_SCORING = "confidence_scoring"
    REVIEW = "review"
    FINALIZED = "finalized"


class StageStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


class ReviewStatus(str, Enum):
    OPEN = "open"
    EDITING = "editing"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


# =============================================================
# P1 - AUTH & USER
# =============================================================

class User(Document):
    """Application user (uploader / reviewer / admin)."""
    email: Indexed(EmailStr, unique=True)
    password_hash: str
    full_name: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"


class RefreshToken(Document):
    """Hashed refresh tokens for JWT rotation."""
    user_id: PydanticObjectId
    token_hash: Indexed(str, unique=True)
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "refresh_tokens"


# =============================================================
# P2 - IMAGE INTAKE & VALIDATION
# =============================================================

class UploadedImage(Document):
    """Raw uploaded image with validation metadata.
    The `processing_id` is the canonical correlation key used by every
    downstream collection (preprocess, OCR, mapping, confidence...).
    """
    processing_id: Indexed(str, unique=True)
    user_id: PydanticObjectId
    original_filename: str
    storage_path: str                       # path / S3 key to original file
    mime_type: str                          # image/jpeg | image/png | image/webp | application/pdf
    file_size: int                          # bytes; max 10 MB enforced in service
    file_hash_sha256: Indexed(str)          # used for duplicate detection
    width: Optional[int] = None
    height: Optional[int] = None
    status: ImageStatus = ImageStatus.RECEIVED
    validation_errors: list[str] = []
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "uploaded_images"


# =============================================================
# P3 - PRE-PROCESSING
# =============================================================

class PreprocessedImage(Document):
    """Post-preprocessing artifact. Original image is preserved unchanged."""
    processing_id: Indexed(str)
    source_image_id: PydanticObjectId
    processed_storage_path: str
    resolution_dpi: int                     # normalized to >= 300
    rotation_applied: int                   # degrees, e.g. 0/90/180/270
    brightness_delta: float = 0.0
    contrast_delta: float = 0.0
    output_format: str = "png"
    preprocessing_status: PreprocessingStatus = PreprocessingStatus.PENDING
    steps_applied: list[str] = []           # e.g. ["resize", "deskew", "contrast"]
    error_message: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "preprocessed_images"


# =============================================================
# P4 - OCR + AI VISION
# =============================================================

class OcrBlock(BaseModel):
    """A single recognized text block from the OCR engine."""
    text: str
    bbox: list[float]                       # [x, y, w, h] in pixels
    confidence: float                       # 0.0 - 1.0


class OcrResult(Document):
    """Raw OCR output kept verbatim for audit / re-review."""
    processing_id: Indexed(str)
    preprocessed_image_id: PydanticObjectId
    ocr_engine: str                         # e.g. "tesseract" | "google_vision"
    raw_text: str
    blocks: list[OcrBlock] = []
    overall_confidence: float
    language_detected: Optional[str] = None
    ocr_version: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ocr_results"


class VisionRegion(BaseModel):
    """A semantic region returned by the vision model (face, MRZ, signature, ...)."""
    label: str                              # e.g. "face", "mrz", "signature", "card_number"
    bbox: list[float]
    confidence: float
    extra: dict[str, Any] = {}


class AiVisionResult(Document):
    """AI-Vision output: document classification + semantic regions."""
    processing_id: Indexed(str)
    preprocessed_image_id: PydanticObjectId
    doc_type: DocType
    doc_type_confidence: float
    detected_regions: list[VisionRegion] = []
    model_name: str                         # e.g. "gemini-1.5-pro"
    model_version: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ai_vision_results"


# =============================================================
# P5 - BUSINESS FIELD MAPPING  (Hui's task)
# =============================================================
# Doc-type specific embedded value objects.
# Storing as discriminated sub-document keeps schema strict per spec.

class PassportFields(BaseModel):
    document_no: Optional[str] = None
    type: Optional[str] = None              # "P"
    country_code: Optional[str] = None      # "AUS"
    surname: Optional[str] = None
    given_names: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None               # "M" | "F" | "X"
    place_of_birth: Optional[str] = None
    date_of_issue: Optional[date] = None
    date_of_expiry: Optional[date] = None
    authority: Optional[str] = None
    mrz_line1: Optional[str] = None
    mrz_line2: Optional[str] = None


class MedicareFields(BaseModel):
    card_number: Optional[str] = None       # 10 digits "1234 56789 1"
    irn: Optional[int] = None               # individual reference number (the leading "1")
    full_name: Optional[str] = None
    valid_to: Optional[str] = None          # "MM/YYYY" - Medicare prints MM/YYYY only


class DriverLicenceFields(BaseModel):
    licence_no: Optional[str] = None
    full_name: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    licence_expiry: Optional[date] = None
    licence_type: Optional[str] = None      # e.g. "CAR"
    conditions: Optional[str] = None        # e.g. "S B E A V X Y Z"
    state: Optional[str] = "VIC"


class FieldValidationResult(BaseModel):
    """Outcome of one business validation rule on one field."""
    field_name: str
    rule: str                               # e.g. "required", "regex_passport_no", "date_in_future"
    passed: bool
    message: Optional[str] = None


class MappedDocument(Document):
    """Structured business data mapped from OCR + Vision results.

    `extracted_fields` holds the raw mapping (1:1 with OCR text);
    `normalized_fields` holds canonical values (ISO dates, trimmed strings,
    upper-cased country codes, etc.).

    IMPORTANT (Acceptance Criteria - P6):
    Fields that cannot be extracted MUST be stored as `null`, not omitted.
    The mapper must emit every expected key for the chosen doc_type, even
    when the value is missing. When serializing to MongoDB, use
    `.model_dump()` (default `exclude_none=False`) - never `exclude_none=True`,
    which would drop missing keys and violate the AC.
    """
    processing_id: Indexed(str, unique=True)
    doc_type: DocType
    user_id: PydanticObjectId
    # Discriminated union - the shape of these dicts matches PassportFields /
    # MedicareFields / DriverLicenceFields based on `doc_type`.
    # Missing values appear as `null`, not as absent keys.
    extracted_fields: dict[str, Any]        # raw mapped values (before normalization)
    normalized_fields: dict[str, Any]       # canonical values (after normalization)
    validation_results: list[FieldValidationResult] = []
    missing_required_fields: list[str] = []
    mapping_status: MappingStatus = MappingStatus.PENDING
    mapper_version: str
    mapped_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "mapped_documents"


# =============================================================
# P6 - CONFIDENCE SCORING & STORAGE
# =============================================================

class FieldConfidence(BaseModel):
    field_name: str
    score: float                            # 0.0 - 1.0
    classification: ConfidenceClass
    auto_approved: bool = False
    note: Optional[str] = None


class ConfidenceReport(Document):
    """Per-document confidence summary used to gate downstream workflows."""
    processing_id: Indexed(str, unique=True)
    mapped_document_id: PydanticObjectId
    field_scores: list[FieldConfidence]
    overall_score: float
    classification: ConfidenceClass
    flags: dict[str, bool] = {}             # e.g. {"requires_manual_review": True}
    failed_fields: list[str] = []
    scored_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "confidence_reports"


class ProcessingHistory(Document):
    """Append-only audit log; one row per stage transition per processing_id."""
    processing_id: Indexed(str)
    stage: ProcessingStage
    status: StageStatus
    details: dict[str, Any] = {}
    ocr_version: Optional[str] = None
    ai_model_version: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "processing_history"


# =============================================================
# P7 - JSON REVIEW
# =============================================================

class EditOperation(BaseModel):
    """Single edit captured during a review session (for audit)."""
    field_name: str
    old_value: Any
    new_value: Any
    edited_at: datetime = Field(default_factory=datetime.utcnow)


class JsonReviewSession(Document):
    """A user-driven review/edit session over a MappedDocument."""
    processing_id: Indexed(str)
    mapped_document_id: PydanticObjectId
    user_id: PydanticObjectId
    current_state: dict[str, Any]           # mutable JSON the user is editing
    edit_log: list[EditOperation] = []
    validation_state: MappingStatus = MappingStatus.PENDING
    review_status: ReviewStatus = ReviewStatus.OPEN
    started_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None

    class Settings:
        name = "json_review_sessions"


class FinalizedDocument(Document):
    """Immutable final JSON after user confirmation; this is the deliverable."""
    processing_id: Indexed(str, unique=True)
    user_id: PydanticObjectId
    doc_type: DocType
    final_json: dict[str, Any]
    source_review_id: PydanticObjectId
    confirmed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "finalized_documents"


# =============================================================
# REGISTER ALL DOCUMENTS (for Beanie init_beanie())
# =============================================================
ALL_DOCUMENTS = [
    User,
    RefreshToken,
    UploadedImage,
    PreprocessedImage,
    OcrResult,
    AiVisionResult,
    MappedDocument,
    ConfidenceReport,
    ProcessingHistory,
    JsonReviewSession,
    FinalizedDocument,
]
