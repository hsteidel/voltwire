from dataclasses import dataclass

from starlette import status


@dataclass
class AppError(Exception):
    message: str
    status_code: int

    def __post_init__(self):
        super().__init__()

    def __str__(self):
        return self.message


@dataclass
class AppWarning(AppError):  # noqa: N818 — intentionally not named *Error; these are expected conditions
    """Raised for expected/recoverable conditions that don't warrant error-level logging."""

    pass


class UnauthorizedRequestError(AppError):
    def __init__(self, message="Unauthorized Request"):
        status_code = status.HTTP_401_UNAUTHORIZED
        super().__init__(message, status_code)


class ForbiddenError(AppWarning):
    def __init__(self, message="Forbidden Request"):
        status_code = status.HTTP_403_FORBIDDEN
        super().__init__(message, status_code)


class BadRequestError(AppError):
    def __init__(self, message="Bad Request"):
        status_code = status.HTTP_400_BAD_REQUEST
        super().__init__(message, status_code)


class EntityNotFoundError(AppError):
    def __init__(self, message="Entity not found"):
        status_code = status.HTTP_404_NOT_FOUND
        super().__init__(message, status_code)

class EntityNotFoundWarning(AppWarning):
    def __init__(self, message="Entity not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)

class ResourceConflictError(AppError):
    def __init__(self, message="Request creates a conflict"):
        status_code = status.HTTP_409_CONFLICT
        super().__init__(message, status_code)

class ResourceConflictWarning(AppWarning):
    def __init__(self, message="Request creates a conflict"):
        status_code = status.HTTP_409_CONFLICT
        super().__init__(message, status_code)

class UnprocessableRequestError(AppError):
    def __init__(self, message="Unprocessable Request"):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        super().__init__(message, status_code)

class UnprocessableRequestWarning(AppWarning):
    def __init__(self, message="Unprocessable Request"):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        super().__init__(message, status_code)


class UnsupportedFeatureError(AppWarning):
    def __init__(self, message="Not implemented"):
        status_code = status.HTTP_501_NOT_IMPLEMENTED
        super().__init__(message, status_code)


class DownstreamServiceError(AppError):
    def __init__(self, message="Downstream service error"):
        status_code = status.HTTP_502_BAD_GATEWAY
        super().__init__(message, status_code)

