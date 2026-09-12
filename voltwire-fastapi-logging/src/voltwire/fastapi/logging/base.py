import logging
import sys
from dataclasses import dataclass
from typing import Protocol

from loguru import logger

from voltwire.fastapi.logging._constants import APP_LOG_FORMAT


class LogSettings(Protocol):
    level: str


@dataclass
class DefaultLogSettings:
    level: str = "INFO"


# Loggers known to attach their own handlers directly (bypassing propagation
# to root) rather than relying on the standard logging tree.
_DIRECTLY_HANDLED_LOGGERS = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "gunicorn",
    "gunicorn.access",
    "gunicorn.error",
    "sqlalchemy",
    "sqlalchemy.engine",
)


class InterceptHandler(logging.Handler):
    """Forwards stdlib `logging` records into loguru.

    Installed on the root logger so any code using plain
    `logging.getLogger(__name__)` (this codebase, other voltwire
    packages, or third-party dependencies) is routed through loguru
    without those callers needing to know loguru exists.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(settings: LogSettings):

    # ensure all python and loguru loggers are clean
    logger.remove()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # some libraries attach handlers directly to their own named logger
    # instead of propagating to root - strip those so they route through
    # the intercept handler too.
    for name in _DIRECTLY_HANDLED_LOGGERS:
        named_logger = logging.getLogger(name)
        named_logger.handlers = []
        named_logger.propagate = True

    logger.add(
        sys.stdout,
        format=APP_LOG_FORMAT,
        level=settings.level,
    )