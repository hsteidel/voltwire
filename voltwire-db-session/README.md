<img src="https://raw.githubusercontent.com/hsteidel/voltwire/main/assets/icons/db-session.svg" alt="" width="56" height="56" align="left">

# voltwire-db-session

A configurable PostgreSQL session factory for Python applications. Wraps SQLAlchemy connection pool setup and pydantic-settings configuration into a single reusable package — install it, point it at your `.env`, and get sessions.

## ORM-agnostic core

`DatabaseSessionFactory`, `RODatabaseSessionFactory`, and `Session` (exported from `voltwire.db.session`) are `Protocol`s, not concrete classes. `TransactionContext` and `DatabaseAutoConfiguration` are written entirely against these interfaces and never import `sqlalchemy` — only `voltwire.db.session.backends.sqlalchemy` does. Today that's the only backend (`SqlAlchemyDatabaseSessionFactory`/`SqlAlchemyRODatabaseSessionFactory`, built via `build_session_factory`/`build_ro_session_factory`), but a future ORM backend only needs to satisfy the same `Protocol`s — no changes required to `TransactionContext`, `DatabaseAutoConfiguration`, or downstream packages like `voltwire-fastapi-db-txs`, which already depend only on the abstraction.

## Installation

```bash
pip install voltwire-db-session
# or with Poetry:
poetry add voltwire-db-session
```

A PostgreSQL driver is **not** included — install whichever you prefer alongside it:

```bash
pip install psycopg2-binary   # most common
pip install psycopg           # psycopg3
```

## Quickstart

```python
from voltwire.db.session import DatabaseSettings, build_session_factory

settings = DatabaseSettings()           # reads DB_* vars from .env
factory = build_session_factory(settings)

session = factory.get_session()
try:
    result = session.execute(...)
    session.commit()
finally:
    session.close()

# On app shutdown
factory.close()
```

## Configuration

All settings are loaded from environment variables with a `DB_` prefix. By default the library reads from a `.env` file in the working directory.

### Environment variables

| Variable              | Default       | Description                                      |
|-----------------------|---------------|--------------------------------------------------|
| `DB_HOST`             | `localhost`   | Primary database host                            |
| `DB_PORT`             | `5432`        | Database port                                    |
| `DB_DATABASE`         | `postgres`    | Database name                                    |
| `DB_USERNAME`         | `postgres`    | Database username                                |
| `DB_PASSWORD`         | `postgres`    | Database password                                |
| `DB_SCHEMA_NAME`      | `public`      | PostgreSQL schema (used for `search_path`)       |
| `DB_DRIVER`           | `psycopg2`    | SQLAlchemy driver name                           |
| `DB_RO_HOST`          | *(unset)*     | Read-only replica host; falls back to `DB_HOST`  |
| `DB_POOL_SIZE`        | `10`          | Minimum connections in pool                      |
| `DB_MAX_POOL_SIZE`    | `20`          | Maximum connections in pool                      |
| `DB_POOL_TIMEOUT`     | `30`          | Seconds to wait for a connection from pool       |
| `DB_POOL_RECYCLE`     | `299`         | Recycle connections after this many seconds      |
| `DB_APPLICATION_NAME` | `app`         | Application name reported to PostgreSQL          |

### Choosing your env file

```python
# Standard .env (default)
settings = DatabaseSettings()

# Custom env file — e.g. .env.local, .env.production
settings = DatabaseSettings.from_env(".env.local")

# No file — reads only from real environment variables
settings = DatabaseSettings.from_env(None)

# No file, with inline overrides
settings = DatabaseSettings.from_env(None, host="db.internal", database="myapp")
```

### Using a different driver

```python
# psycopg3
settings = DatabaseSettings.from_env(".env", driver="psycopg")

# or via env var
# DB_DRIVER=psycopg
```

The `driver` value is used as the SQLAlchemy URL scheme: `postgresql+{driver}://...`. The corresponding package must be installed in your environment.

## Read-only replica

```python
from voltwire.db.session import DatabaseSettings, build_ro_session_factory

settings = DatabaseSettings()       # set DB_RO_HOST to point at your replica
ro_factory = build_ro_session_factory(settings)

session = ro_factory.get_session()  # writes will be rejected by PostgreSQL
```

If `DB_RO_HOST` is not set, `RODatabaseSessionFactory` falls back to the primary host but still enforces read-only mode at the PostgreSQL level.

## FastAPI example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from voltwire.db.session import DatabaseSettings, build_session_factory

settings = DatabaseSettings.from_env(".env.local")

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = build_session_factory(settings)
    yield
    app.state.db.close()

app = FastAPI(lifespan=lifespan)

@app.get("/items")
def list_items():
    session = app.state.db.get_session()
    try:
        return session.execute(...).all()
    finally:
        session.close()
```

## Logging

The library emits to the `voltwire.db.session` logger namespace using Python's standard `logging` module. To activate debug output:

```python
import logging
logging.getLogger("voltwire.db.session").setLevel(logging.DEBUG)
```

### Routing to loguru

If your app uses [loguru](https://github.com/Delgan/loguru), intercept stdlib logging once at startup:

```python
import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logger.opt(depth=6, exception=record.exc_info).log(
            record.levelname, record.getMessage()
        )

logging.getLogger("voltwire.db.session").addHandler(InterceptHandler())
```
