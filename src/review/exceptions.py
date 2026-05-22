from src.exceptions import AppException


class InvalidState(AppException):
    status_code = 400
    code = "INVALID_STATE"
    message = "Document is not in a valid state for this operation"


class AlreadyFinalized(AppException):
    status_code = 400
    code = "INVALID_STATE"
    message = "Document has already been finalized"


class SessionExpired(AppException):
    status_code = 400
    code = "INVALID_STATE"
    message = "Review session has expired"
