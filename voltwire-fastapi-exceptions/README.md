<img src="https://raw.githubusercontent.com/hsteidel/voltwire/main/assets/icons/fastapi-exceptions.svg" alt="" width="56" height="56" align="left">

# voltwire-fastapi-exceptions

Reusable exception handling for FastAPI apps: a base `AppError` hierarchy you can raise
(and extend), plus a middleware + validation handler so that **every** error — raised before,
during, or after the route — reaches the client as the same JSON body.

**Bring your own response model.** The library never defines or imposes a response schema —
you pass your own model down, and the handlers use only the slice they need (construct it with
`message` + `errors`, then call `.model_dump()`). Your app keeps one model for both success and
error responses; nothing is coupled across the boundary.

## Installation

```bash
pip install voltwire-fastapi-exceptions
# or with Poetry:
poetry add voltwire-fastapi-exceptions
```

## Raising errors

Raise an `AppError` (or a subclass) anywhere; the middleware turns it into your response
model with the right status code.

```python
from voltwire.fastapi.exceptions import EntityNotFoundError, ForbiddenError

def get_user(user_id: str):
    user = repo.find(user_id)
    if not user:
        raise EntityNotFoundError(f"No user {user_id}")   # -> 404
    if not user.active:
        raise ForbiddenError()                            # -> 403
    return user
```

Built-in classes: `UnauthorizedRequestError` (401), `ForbiddenError` (403),
`BadRequestError` (400), `EntityNotFoundError` (404), `ResourceConflictError` (409),
`UnprocessableRequestError` (422), `UnsupportedFeatureError` (501),
`DownstreamServiceError` (502).

`AppWarning` is an `AppError` subclass for **expected/recoverable** conditions — logged
at `warning` level instead of `error`. `ForbiddenError` and `UnsupportedFeatureError` are
warnings.

### Extend them

```python
from voltwire.fastapi.exceptions import UnprocessableRequestError

class DivideByZeroError(UnprocessableRequestError):
    def __init__(self, message="Cannot divide by zero"):
        super().__init__(message)
```

## Your response model

Provide any model whose instances have a `.model_dump()` and that can be constructed with
`message=` and `errors=` (a pydantic model with those two fields — plus whatever else you want,
e.g. `timestamp`, `metadata` — is the common case). The library only ever sets `message` and
`errors`; the rest come from your model's defaults. This is the `ApiErrorBody` protocol:

```python
class ApiErrorBody(Protocol):
    def __init__(self, *, message: str, errors: list[str]) -> None: ...
    def model_dump(self, *, mode: str = "json", exclude_none: bool = True) -> dict: ...
```

## Wiring it into your app

```python
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from voltwire.fastapi.exceptions import (
    ExceptionMiddleware,
    DefaultExceptionHandlerSettings,
    build_validation_handler,
    build_error_responses,
)
from myapp.models import ApiMessage   # <-- YOUR model

app = FastAPI(responses=build_error_responses(ApiMessage))   # OpenAPI error schemas

# Catches AppError (-> its status) and any unexpected Exception (-> 500).
app.add_middleware(
    ExceptionMiddleware,
    error_model=ApiMessage,
    settings=DefaultExceptionHandlerSettings(production=is_production()),
)

# RequestValidationError is raised during request parsing, before the middleware runs,
# so register it as an exception handler too — same body, built from your model.
app.add_exception_handler(RequestValidationError, build_validation_handler(ApiMessage))
```

## Settings (why not read your env directly?)

The middleware only needs to know one thing: **are we in production?** (In production the 500
handler hides the raw exception string; otherwise it includes it to aid debugging.)

Rather than force a settings system on you, it takes any object matching the
`ExceptionHandlerSettings` protocol — a single `production: bool`. Use the provided
`DefaultExceptionHandlerSettings`, or pass your own object exposing `production`.

## Logging

Handlers log via `logging.getLogger(__name__)` (Python's standard `logging` module) —
`AppWarning` at `warning`, real errors at `error`/`exception`. To activate debug output:

```python
import logging
logging.getLogger("voltwire.fastapi.exceptions").setLevel(logging.DEBUG)
```

If your app uses [loguru](https://github.com/Delgan/loguru), intercept stdlib logging once at startup:

```python
import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logger.opt(depth=6, exception=record.exc_info).log(
            record.levelname, record.getMessage()
        )

logging.getLogger("voltwire.fastapi.exceptions").addHandler(InterceptHandler())
```
