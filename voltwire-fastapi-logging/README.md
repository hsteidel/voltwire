<img src="https://raw.githubusercontent.com/hsteidel/voltwire/main/assets/icons/fastapi-logging.svg" alt="" width="56" height="56" align="left">

# voltwire-fastapi-logging

Logging utilities for FastAPI apps: request-context-enriching middleware.

## Installation

```bash
pip install voltwire-fastapi-logging
```

## Quickstart

```python
from voltwire.fastapi.logging import setup_logging, DefaultLogSettings

setup_logging(DefaultLogSettings(enable_json=False, level="INFO"))
```

Add `LoggingContextMiddleware` to enrich every log entry within a request with a correlation
ID, method, and path:

```python
from voltwire.fastapi.logging import LoggingContextMiddleware, DefaultLoggingMiddlewareSettings

app.add_middleware(LoggingContextMiddleware, settings=DefaultLoggingMiddlewareSettings())
```
