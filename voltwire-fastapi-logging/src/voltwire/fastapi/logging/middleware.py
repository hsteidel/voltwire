from dataclasses import dataclass, field
from typing import Protocol, Callable, Awaitable, Any

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from voltwire.fastapi.logging._constants import log_context

ContextEnricher = Callable[[Request, dict[str, Any]], Awaitable[None]]


class LoggingMiddlewareSettings(Protocol):
    context_enrichers: list[ContextEnricher]

@dataclass
class DefaultLoggingMiddlewareSettings:
    context_enrichers: list[ContextEnricher] = field(default_factory=list)

class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    This middleware enriches every log entry with request context.
    - Adds method and path to all logs within the request scope
    - Executes custom context enrichers to add additional context
    
    Custom context enrichers can be registered via settings:
        async def custom_enricher(request: Request, context: dict[str, Any]) -> None:
            context["custom_field"] = "custom_value"
        
        settings = DefaultLoggingMiddlewareSettings(
            context_enrichers=[custom_enricher]
        )
        app.add_middleware(LoggingContextMiddleware, settings=settings)
    """

    def __init__(self, app, settings: LoggingMiddlewareSettings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        request_context = {"method": request.method, "path": request.url.path}

        # Execute custom context enrichers
        for enricher in self.settings.context_enrichers:
            try:
                await enricher(request, request_context)
            except Exception as e:
                logger.warning(f"Context enricher {enricher.__name__} failed: {str(e)}")

        # Process the request within loguru context
        with log_context(**request_context):
            logger.trace(f"Request started: {request.method} {request.url.path}")
            response = await call_next(request)
            logger.trace(f"Request completed: {request.method} {request.url.path} - {response.status_code}")
            return response