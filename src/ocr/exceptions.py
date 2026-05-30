from src.exceptions import AppException


class OcrFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "OCR extraction failed"
class CardNotDetected(AppException):
    status_code = 500
    code = "CARD_NOT_DETECTED"
    message = "Card not detected"

class ExtractionTimeout(AppException):
    status_code = 500
    code = "EXTRACTION_TIMEOUT"
    message = "Extraction timeout"

class VisionApiError(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "AI Vision API error"


class ApiQuotaExceeded(AppException):
    status_code = 429
    code = "PIPELINE_FAILED"
    message = "Vision API quota exceeded"
