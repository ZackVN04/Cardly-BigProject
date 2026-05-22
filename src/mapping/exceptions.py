from src.exceptions import AppException


class MappingFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Business field mapping failed"


class SchemaMismatch(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "OCR output does not match expected schema"


class UnknownDocType(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Unknown document type"
