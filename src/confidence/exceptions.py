from src.exceptions import AppException


class DocumentNotFound(AppException):
    status_code = 404
    code = "NOT_FOUND"
    message = "Document not found"


class ScoringFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Confidence scoring failed"


class UnsupportedDocumentType(AppException):
    status_code = 422
    code = "UNSUPPORTED_DOCUMENT_TYPE"
    message = "P6 confidence scoring currently supports business_card only"
