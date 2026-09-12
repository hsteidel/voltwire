<img src="https://raw.githubusercontent.com/hsteidel/voltwire/main/assets/icons/di-core.svg" alt="" width="56" height="56" align="left">

# voltwire-di-core

A small, framework-agnostic dependency-injection framework for Python. Decorate your classes with `@component`, point the auto-discovery scanner at your package, and get a wired global container — no manual registration boilerplate. Works in a FastAPI app, a plain script, an AWS Lambda, or anywhere else.

Built on [`dependency-injector`](https://python-dependency-injector.ets-labs.org/) for the underlying provider machinery.

## Installation

```bash
pip install voltwire-di-core
# or with Poetry:
poetry add voltwire-di-core
```

## Quickstart

Mark the classes you want managed with `@component` (pairs naturally with `@attrs.define`):

```python
import attrs
from voltwire.di.core import component


@component
@attrs.define
class GreetingRepository:
    def greeting(self) -> str:
        return "hello"


@component
@attrs.define
class GreetingService:
    _repo: GreetingRepository

    def greet(self) -> str:
        return self._repo.greeting()
```

At startup, scan your package once and then resolve anything:

```python
from voltwire.di.core import auto_discover_components, di

auto_discover_components(base_package="myapp")

service = di.provide(GreetingService)   # GreetingRepository injected automatically
service.greet()
```

Constructor dependencies are resolved from their type hints. Registration is multi-pass, so the order in which components are discovered does not matter. Parameters **with default values are treated as optional** and skipped, and an `Optional[T]` / `T | None` dependency is skipped when no provider for `T` exists.

Need exactly one shared instance instead of a new one per `di.provide`? Use `@singleton` instead of `@component` — it participates in the same auto-discovery and multi-pass dependency resolution, but is wired up with a `providers.Singleton` instead of a factory:

```python
from voltwire.di.core import singleton


@singleton
class CacheService:
    def __init__(self, settings: CacheSettings):
        self._settings = settings
```

This is a drop-in alternative to manually calling `di.register_singleton(...)` after discovery — use whichever fits: `@singleton` for classes discovered by scanning your package, `di.register_singleton` for one-offs (e.g. third-party clients) inside a `registrars` callback.

## How resolution works

`auto_discover_components(base_package, registrars=None)` runs in three steps:

1. **`@settings` functions** are registered first as singletons (see below).
2. **`registrars`** — optional callbacks for manual singletons that need special construction (e.g. third-party clients) — are invoked.
3. **`@component` classes** are registered with multi-pass dependency resolution.

```python
from voltwire.di.core import auto_discover_components, di


def register_external_clients() -> None:
    di.register_singleton(SomeClient, api_key="...")


auto_discover_components(base_package="myapp", registrars=[register_external_clients])
```

## Settings providers

Use `@settings` on a function whose return type is the type to register. Combine with `functools.lru_cache` for single instantiation:

```python
from functools import lru_cache
from voltwire.di.core import settings


@settings
@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()
```

The returned instance is registered as a singleton keyed by the return annotation, so any `@component` depending on `DatabaseSettings` receives it.

## Core providers (app-supplied)

`voltwire-di-core` ships **no** opinionated providers — it is deliberately decoupled from databases, sessions, and web frameworks. Your application supplies its own "core" providers (things that must exist before anything is resolved, e.g. a DB session factory) by registering one or more callables on the container. They run **once**, lazily, the first time anything is provided:

```python
from voltwire.di.core import di


def register_db_providers() -> None:
    di.register(DatabaseSettings, providers.Object(get_db_settings()))
    di.register_singleton(SessionFactory, settings=di.get_provider(DatabaseSettings))


di.register_core_provider(register_db_providers)

# First di.provide(...) anywhere triggers ensure_core_providers() internally.
di.provide(SessionFactory)
```

You can also drive this explicitly via `di.ensure_core_providers()`. Initialization is guarded by a lock and a one-time flag, so it is safe to call repeatedly. Register core providers at startup, before the first `di.provide`.

## Public API

```python
from voltwire.di.core import (
    component,                       # class decorator → register for auto-discovery (factory)
    singleton,                       # class decorator → register for auto-discovery (singleton)
    settings,                        # function decorator → register a singleton by return type
    auto_discover_components,        # scan a package and wire the container

    di,                               # di.provide / di.register / di.register_factory / di.register_singleton /
                                      # di.get_provider / di.provider_exists / di.register_core_provider /
                                      # di.ensure_core_providers

    dependency_container,            # the DependencyContainer singleton
    DependencyContainer,             # the container type
    get_component_registry,          # introspection: everything @component/@singleton/@settings collected
    analyze_component_dependencies,  # introspection: a class's required constructor deps
    is_singleton_component,          # introspection: was this class marked @singleton?

    providers,                       # re-export of dependency_injector.providers (Object/Factory/Singleton/Callable)
    containers,                      # re-export of dependency_injector.containers
)
```

`providers` and `containers` are re-exported so consumers can build custom providers (e.g. `providers.Object(instance)`) without importing `dependency-injector` directly — this library is the single DI surface.

## FastAPI

The framework intentionally does **not** import FastAPI. To expose a component to routes, write the small glue in your app:

```python
from typing import Annotated
from fastapi import Depends, Request
from voltwire.di.core import dependency_container

# Make the container available on app.state at startup:
#   application.state.provide = dependency_container().provide

def build(request: Request) -> GreetingService:
    return request.app.state.provide(GreetingService)

GreetingServiceDI = Annotated[GreetingService, Depends(build)]
```

## Logging

The library emits to per-module `logging.getLogger(__name__)` loggers under `voltwire.di.core.*` using Python's standard `logging` module (mostly at `debug`). Registration/resolution failures log at `error`. To activate debug output:

```python
import logging
logging.getLogger("voltwire.di.core").setLevel(logging.DEBUG)
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

logging.getLogger("voltwire.di.core").addHandler(InterceptHandler())
```
