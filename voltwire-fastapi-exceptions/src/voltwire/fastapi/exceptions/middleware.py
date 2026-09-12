import logging
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from voltwire.fastapi.exceptions.exceptions import AppError, AppWarning

logger = logging.getLogger(__name__)


class ApiErrorBody(Protocol):
    def __init__(self, *, message: str, errors: list[str]) -> None: ...

    def model_dump(self, *, mode: str = "json", exclude_none: bool = True) -> dict[str, Any]: ...


class ExceptionHandlerSettings(Protocol):
    production: bool


@dataclass
class DefaultExceptionHandlerSettings:
    production: bool = False


def _handle_unexpected_error(
    request: Request, e: Exception, settings: ExceptionHandlerSettings, error_model: type[ApiErrorBody]
) -> JSONResponse:
    logger.exception("Internal server error occurred", extra={"path": request.url.path})
    errors = [] if settings.production else [str(e)]
    body = error_model(message="internal server error", errors=errors)
    return JSONResponse(
        content=body.model_dump(mode="json", exclude_none=True),
        media_type="application/json",
        status_code=500,
    )


def _handle_service_error(request: Request, e: AppError, error_model: type[ApiErrorBody]) -> JSONResponse:
    if isinstance(e, AppWarning):
        logger.warning(
            "Expected service condition",
            extra={"path": request.url.path, "error_type": type(e).__name__},
        )
    else:
        logger.exception(
            "Service error occurred",
            extra={"path": request.url.path, "error_type": type(e).__name__},
        )
    body = error_model(message="service error", errors=[e.message])
    response_content = body.model_dump(mode="json", exclude_none=True)
    if not isinstance(e, AppWarning):
        logger.error(f"AppError response - status: {e.status_code}, content: {response_content}")
    return JSONResponse(
        content=response_content,
        media_type="application/json",
        status_code=e.status_code,
    )


def build_validation_handler(error_model: type[ApiErrorBody]):
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(f"Validation error details: {exc.errors()}")
        errors = []
        for error in exc.errors():
            location = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            message = error["msg"]
            error_type = error.get("type", "unknown")
            detailed_error = (
                f"Field: {location if location else 'N/A'}, Error: {message}, Type: {error_type}, Received: "
                f"{error.get('input', 'not provided')}"
            )
            errors.append(detailed_error)
            logger.warning(detailed_error)
        body = error_model(message="Request Validation Error", errors=errors)
        return JSONResponse(
            status_code=422,
            content=body.model_dump(mode="json", exclude_none=True),
        )

    return handle_validation_error


def build_error_responses(error_model: type[ApiErrorBody]) -> dict:
    return {
        401: {
            "model": error_model,
            "description": "Authentication data in the request is invalid",
        },
        403: {"model": error_model, "description": "Not authorized"},
        404: {"model": error_model, "description": "Not found"},
        409: {"model": error_model, "description": "Resource conflict detected"},
        422: {
            "model": error_model,
            "description": "Understood the request, but can't and won't process it",
        },
        400: {"model": error_model, "description": "Bad request"},
    }


class ExceptionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, error_model: type[ApiErrorBody], settings: ExceptionHandlerSettings | None = None):
        super().__init__(app)
        self._error_model = error_model
        self._settings = settings or DefaultExceptionHandlerSettings()

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppError as e:
            return _handle_service_error(request, e, self._error_model)
        except Exception as e:
            return _handle_unexpected_error(request, e, self._settings, self._error_model)
