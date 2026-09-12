__version__ = "0.0.0"

from typing import Any, Protocol

from pydantic import BaseModel

from voltwire.fastapi.logging._constants import log_context
from voltwire.fastapi.logging.middleware import ContextEnricher

__all__ = ["ContextEnricher", "log_context", "integration_logger", "log_banner", "IntegrationLogContext", "AppRuntimeSettings"]


class IntegrationLogContext(BaseModel):
    integration: str
    message: str


class AppRuntimeSettings(Protocol):
    app_name: str
    version: str
    environment: str


def log_banner(settings: AppRuntimeSettings):
    print(
        f"Application: '{settings.app_name}' Version: '{settings.version}' Environment: '{settings.environment}'",
        flush=True,
    )


def integration_logger(context: IntegrationLogContext, **extra: Any):
    from loguru import logger

    context_dict = {**context.model_dump(), **extra}
    return logger.contextualize(**context_dict)
