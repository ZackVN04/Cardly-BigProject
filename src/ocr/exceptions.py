from src.exceptions import AppException


class OcrFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "OCR extraction failed"


class CardNotDetected(AppException):
    status_code = 422
    code = "CARD_NOT_DETECTED"
    message = "No business card could be detected in the uploaded image."


class ExtractionTimeout(AppException):
    status_code = 504
    code = "EXTRACTION_TIMEOUT"
    message = "Business card extraction exceeded the maximum allowed processing time."


class OcrSaveFailed(AppException):
    status_code = 500
    code = "OCR_SAVE_FAILED"
    message = "Failed to persist OCR result."


class GeminiExtractionFailed(AppException):
    status_code = 502
    code = "GEMINI_EXTRACTION_FAILED"
    message = "The AI extraction service returned an invalid response."


class VisionApiError(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "AI Vision API error"


class ApiQuotaExceeded(AppException):
    status_code = 429
    code = "PIPELINE_FAILED"
    message = "Vision API quota exceeded"
