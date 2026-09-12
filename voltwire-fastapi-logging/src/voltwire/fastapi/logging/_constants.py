from typing import Any

from loguru import logger

APP_LOG_FORMAT = (
    "<level>{level}</level>: <green>{time:YYYY-MM-DDTHH:mm:s:SSS!UTC}</green> "
    "| {process}:{thread} | {name}:{line} - {message} | {extra}"
)

def log_context(**extra: Any):
    return logger.contextualize(**extra)
