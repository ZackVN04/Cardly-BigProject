from src.exceptions import AppException


class PreprocessFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Image preprocessing failed"


class ImageDistorted(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Image distortion detected during preprocessing"


class MemoryOverflow(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Memory overflow during image processing"
