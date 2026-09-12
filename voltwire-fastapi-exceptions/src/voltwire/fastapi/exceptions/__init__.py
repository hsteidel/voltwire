from voltwire.fastapi.exceptions.exceptions import *  # noqa: F401, F403
from voltwire.fastapi.exceptions.middleware import (
    ApiErrorBody,
    DefaultExceptionHandlerSettings,
    ExceptionHandlerSettings,
    ExceptionMiddleware,
    build_error_responses,
    build_validation_handler,
)

__version__ = "0.0.0"

__all__ = [
    "AppError",
    "AppWarning",
    "UnauthorizedRequestError",
    "ForbiddenError",
    "BadRequestError",
    "EntityNotFoundError",
    "EntityNotFoundWarning",
    "ResourceConflictError",
    "ResourceConflictWarning",
    "UnprocessableRequestError",
    "UnprocessableRequestWarning",
    "UnsupportedFeatureError",
    "DownstreamServiceError",
    "ExceptionMiddleware",
    "build_validation_handler",
    "build_error_responses",
    "ApiErrorBody",
    "ExceptionHandlerSettings",
    "DefaultExceptionHandlerSettings",
]
