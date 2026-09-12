<p align="center">
  <img src="logo.png" alt="voltwire" width="320">
</p>

# voltwire

A small collection of FastAPI bolt-on libraries inspired by battle-tested production patterns.

## Packages

| | Package | Description                                                      |
|---|---|------------------------------------------------------------------|
| <img src="assets/icons/di-core.svg" width="28" height="28"> | [voltwire-di-core](voltwire-di-core) | DI container & component auto-discovery                          |
| <img src="assets/icons/db-session.svg" width="28" height="28"> | [voltwire-db-session](voltwire-db-session) | Configurable database session factory                            |
| <img src="assets/icons/db-types-json.svg" width="28" height="28"> | [voltwire-db-types-json](voltwire-db-types-json) | Custom SQLAlchemy JSONB column types backed by Pydantic models   |
| <img src="assets/icons/fastapi-exceptions.svg" width="28" height="28"> | [voltwire-fastapi-exceptions](voltwire-fastapi-exceptions) | Reusable FastAPI exception hierarchy + unified exception handler |
| <img src="assets/icons/fastapi-logging.svg" width="28" height="28"> | [voltwire-fastapi-logging](voltwire-fastapi-logging) | Logging utilities for FastAPI apps                               |
| <img src="assets/icons/fastapi-db-txs.svg" width="28" height="28"> | [voltwire-fastapi-db-txs](voltwire-fastapi-db-txs) | FastAPI middleware more managing request-scoped DB transactions  |

## Development

This repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/). From the repo root:

```bash
uv sync --all-packages                              # install all packages + dev dependencies
uv run --project voltwire-db-session pytest         # run a single package's tests
for d in voltwire-*; do (cd "$d" && uv run pytest -q); done   # run every package's tests
```

Each package remains independently installable and publishable — the workspace only exists
to make local development and cross-package testing convenient.

## License

MIT
