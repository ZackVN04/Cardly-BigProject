from enum import Enum


class DocType(str, Enum):
    BUSINESS_CARD = "business_card"
    UNKNOWN = "unknown"


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
