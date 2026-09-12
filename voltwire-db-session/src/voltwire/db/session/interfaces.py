"""
ORM-agnostic interfaces (Spring-style facade)

Everything outside of ``voltwire.db.session.backends`` — ``TransactionContext``,
``DatabaseAutoConfiguration``, and downstream packages like ``voltwire-fastapi-db-txs``
— is written against these ``Protocol``s rather than any concrete ORM type. Today the
only implementation is SQLAlchemy-backed (see ``voltwire.db.session.backends.sqlalchemy``),
but nothing outside that module imports ``sqlalchemy`` — a future backend (e.g. an
async ORM) only needs to satisfy ``DatabaseSessionFactory``/``Session`` structurally,
with no changes required to ``TransactionContext`` or consuming apps.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Session(Protocol):
    """The minimal session surface ``TransactionContext`` relies on."""

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class DatabaseSessionFactory(Protocol):
    """Produces sessions backed by a connection pool for a single logical database."""

    def get_session(self) -> Session: ...

    def get_engine(self) -> Any: ...

    def close(self) -> None: ...


@runtime_checkable
class RODatabaseSessionFactory(DatabaseSessionFactory, Protocol):
    """A :class:`DatabaseSessionFactory` that targets a read-only replica.

    Carries no additional methods — the read-only guarantee is a construction-time/
    backend-level concern (e.g. ``postgresql_readonly=True`` for the SQLAlchemy
    backend), not part of the shared interface.
    """
