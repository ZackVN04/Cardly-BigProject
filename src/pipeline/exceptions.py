from src.exceptions import AppException


class PipelineFailed(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Pipeline execution failed"


class StageTimeout(AppException):
    status_code = 500
    code = "PIPELINE_FAILED"
    message = "Pipeline stage timed out"
