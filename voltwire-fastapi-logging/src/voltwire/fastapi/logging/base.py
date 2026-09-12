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


def setup_logging(settings: LogSettings):

    # ensure all python and loguru loggers are clean
    logger.remove()
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    logger.add(
        sys.stdout,
        format=APP_LOG_FORMAT,
        level=settings.level,
    )