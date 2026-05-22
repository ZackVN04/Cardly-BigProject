from src.exceptions import AppException


class DocumentNotFound(AppException):
    status_code = 404
    code = "NOT_FOUND"
    message = "Document not found"


class ScoringFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Confidence scoring failed"
