# =============================================================
# Cardly — AI-Powered Business Card Scanner & Smart Contact Forge
# MongoDB Schemas
# Stack: FastAPI + Beanie ODM (async MongoDB) + Pydantic v2
# =============================================================
# Comments in English to keep codebase consistent.
# Each Collection below maps to a Beanie Document class.
# =============================================================

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Annotated
from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field


# =============================================================
# ENUMS (shared across collections)
# =============================================================

class UserRole(str, Enum):
    USER = "user"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class DocType(str, Enum):
    BUSINESS_CARD = "business_card"
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


class OtpPurpose(str, Enum):
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"


# =============================================================
# P1 - AUTH & USER
# =============================================================

class User(Document):
    """Application user (uploader / reviewer / admin)."""
    email: Annotated[EmailStr, Indexed(unique=True)]
    password_hash: str
    full_name: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    verification_token: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"


class RefreshToken(Document):
    """Hashed refresh tokens for JWT rotation."""
    user_id: PydanticObjectId
    token_hash: Annotated[str, Indexed(unique=True)]
    expires_at: datetime
    revoked: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "refresh_tokens"


class OtpToken(Document):
    """6-digit OTP for password reset / email verification.
    OTP is valid for 5 minutes. Only the latest OTP per user+purpose is valid.
    """
    user_id: PydanticObjectId
    otp_hash: str                           # hashed 6-digit code
    purpose: OtpPurpose
    expires_at: datetime                    # created_at + 5 minutes
    used: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "otp_tokens"


class LoginAttempt(Document):
    """Tracks failed login attempts for account lockout.
    After 5 consecutive failures, the account is locked for 60 seconds.
    """
    email: Annotated[str, Indexed()]
    failed_count: int = 0
    locked_until: Optional[datetime] = None
    last_attempt_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "login_attempts"


# =============================================================
# P2 - IMAGE INTAKE & VALIDATION
# =============================================================

class UploadedImage(Document):
    """Raw uploaded business card image(s) with validation metadata.
    The `processing_id` is the canonical correlation key used by every
    downstream collection (preprocess, OCR, mapping, confidence...).
    """
    processing_id: Annotated[str, Indexed(unique=True)]
    user_id: PydanticObjectId
    original_filename: str
    storage_paths: list[str] = []           # paths / S3 keys to original files (e.g. [front, back])
    mime_type: str                          # image/jpeg | image/png | image/webp | application/pdf
    file_size: int                          # bytes; max 10 MB enforced in service
    file_hash_sha256: Annotated[str, Indexed()]          # used for duplicate detection
    width: Optional[int] = None
    height: Optional[int] = None
    status: ImageStatus = ImageStatus.RECEIVED
    quality_check: dict[str, Any] = {}      # quality metrics: {"tilt": float, "blur": float, "brightness": float}
    validation_errors: list[str] = []
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "uploaded_images"


# =============================================================
# P3 - PRE-PROCESSING
# =============================================================

class PreprocessedImage(Document):
    """Post-preprocessing artifact. Original image is preserved unchanged."""
    processing_id: Annotated[str, Indexed()]
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
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    processing_id: Annotated[str, Indexed()]
    preprocessed_image_id: PydanticObjectId
    ocr_engine: str                         # e.g. "tesseract" | "gemini"
    raw_text: str
    blocks: list[OcrBlock] = []
    overall_confidence: float
    language_detected: Optional[str] = None
    ocr_version: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "ocr_results"


class VisionRegion(BaseModel):
    """A semantic region returned by the vision model (name, phone, email, ...)."""
    label: str                              # e.g. "name", "phone", "email", "company", "position", "web"
    bbox: list[float]
    confidence: float
    extra: dict[str, Any] = {}


class AiVisionResult(Document):
    """AI-Vision output: document classification + semantic regions."""
    processing_id: Annotated[str, Indexed()]
    preprocessed_image_id: PydanticObjectId
    doc_type: DocType
    doc_type_confidence: float
    detected_regions: list[VisionRegion] = []
    model_name: str                         # e.g. "gemini-3.1-pro"
    model_version: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "ai_vision_results"


# =============================================================
# P5 - BUSINESS FIELD MAPPING
# =============================================================

class BusinessCardFields(BaseModel):
    """Extracted and enriched fields from a business card.
    All fields are Optional so that partial extraction is valid.
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    web: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    
    # AI Enrichment & Classification
    industry: Optional[str] = None          # e.g. Technology, Finance, Education...
    summary: Optional[str] = None           # 2-4 sentence professional brief
    keywords: list[str] = []                # list of tags, e.g. ["AI startup", "renewable energy"]
    highlights: list[str] = []              # key highlights, e.g. ["Recently raised Series A"]


class FieldValidationResult(BaseModel):
    """Outcome of one business validation rule on one field."""
    field_name: str
    rule: str                               # e.g. "required", "email_format", "phone_format"
    passed: bool
    message: Optional[str] = None


class MappedDocument(Document):
    """Structured business data mapped from OCR + Vision results.

    `extracted_fields` holds the raw mapping (1:1 with OCR text);
    `normalized_fields` holds canonical values (trimmed strings,
    standardized phone format, lowercase email, etc.).
    """
    processing_id: Annotated[str, Indexed(unique=True)]
    doc_type: DocType = DocType.BUSINESS_CARD
    user_id: PydanticObjectId
    
    # Both fields follow BusinessCardFields shape
    extracted_fields: dict[str, Any]        # raw mapped values (before normalization)
    normalized_fields: dict[str, Any]       # canonical values (after normalization)
    validation_results: list[FieldValidationResult] = []
    missing_required_fields: list[str] = []
    mapping_status: MappingStatus = MappingStatus.PENDING
    mapper_version: str
    mapped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    processing_id: Annotated[str, Indexed(unique=True)]
    mapped_document_id: PydanticObjectId
    field_scores: list[FieldConfidence]
    overall_score: float
    classification: ConfidenceClass
    flags: dict[str, bool] = {}             # e.g. {"requires_manual_review": True}
    failed_fields: list[str] = []
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "confidence_reports"


class ProcessingHistory(Document):
    """Append-only audit log; one row per stage transition per processing_id."""
    processing_id: Annotated[str, Indexed()]
    stage: ProcessingStage
    status: StageStatus
    details: dict[str, Any] = {}
    ocr_version: Optional[str] = None
    ai_model_version: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    edited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JsonReviewSession(Document):
    """A user-driven review/edit session over a MappedDocument."""
    processing_id: Annotated[str, Indexed()]
    mapped_document_id: PydanticObjectId
    user_id: PydanticObjectId
    current_state: dict[str, Any]           # mutable JSON the user is editing (BusinessCardFields shape)
    edit_log: list[EditOperation] = []
    validation_state: MappingStatus = MappingStatus.PENDING
    review_status: ReviewStatus = ReviewStatus.OPEN
    
    # Smart Tagging & Context Metadata
    event_name: Optional[str] = None
    location: Optional[str] = None
    meeting_date: Optional[datetime] = None
    custom_tags: list[str] = []
    
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None

    class Settings:
        name = "json_review_sessions"


class FinalizedDocument(Document):
    """Immutable final JSON after user confirmation; this is the deliverable."""
    processing_id: Annotated[str, Indexed(unique=True)]
    user_id: PydanticObjectId
    doc_type: DocType = DocType.BUSINESS_CARD
    final_json: dict[str, Any]              # finalized fields (BusinessCardFields shape)
    
    # Smart Tagging & Context Metadata
    event_name: Optional[str] = None
    location: Optional[str] = None
    meeting_date: Optional[datetime] = None
    custom_tags: list[str] = []
    
    source_review_id: PydanticObjectId
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "finalized_documents"


# =============================================================
# REGISTER ALL DOCUMENTS (for Beanie init_beanie())
# =============================================================
ALL_DOCUMENTS = [
    User,
    RefreshToken,
    OtpToken,
    LoginAttempt,
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
