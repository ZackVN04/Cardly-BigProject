from src.exceptions import AppException


class OcrFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "OCR extraction failed"


class VisionApiError(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "AI Vision API error"


class ApiQuotaExceeded(AppException):
    status_code = 429
    code = "PIPELINE_FAILED"
    message = "Vision API quota exceeded"
