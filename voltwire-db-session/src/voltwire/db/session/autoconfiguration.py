"""
Database Autoconfiguration

Given ``DatabaseSettings`` (and optional properties for sane defaults), wires up the
components a consuming app needs for DB session + transaction management, so app
startup is a single call instead of hand-assembling each piece.

Usage::

    db = auto_configure_database(get_db_settings())

    # if using with di
    container.register(DatabaseSessionFactory, providers.Object(db.session_factory))
    container.register(TransactionContext, providers.Object(db.transaction_context))

    # if using fastapi tx middleware
    app.add_middleware(
        TransactionMiddleware,
        transaction_context=db.transaction_context,
        session_factory=db.session_factory,
    )
"""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

from voltwire.db.session.backends.sqlalchemy import build_ro_session_factory, build_session_factory
from voltwire.db.session.interfaces import DatabaseSessionFactory, RODatabaseSessionFactory, Session
from voltwire.db.session.settings import DatabaseSettings
from voltwire.db.session.transaction import TransactionContext


@dataclass
class DatabaseAutoConfigurationProperties:
    """Optional knobs for ``auto_configure_database``."""

    build_read_replica: bool = False
    on_start_transaction: Callable[[DatabaseSessionFactory], None] | None = None
    """
    Called with the ``DatabaseSessionFactory`` before ``transaction_context()``/
    ``transaction()`` opens a session for an explicit script/background-task
    transaction. Not called for sessions opened by FastAPI middleware. Use this for
    validation that should only run outside the request path — e.g. asserting the
    factory points at a test database during a pytest run.
    """


@dataclass
class DatabaseAutoConfiguration:
    """Wired DB components for a process, given ``DatabaseSettings`` + properties."""

    session_factory: DatabaseSessionFactory
    transaction_context: TransactionContext
    ro_session_factory: RODatabaseSessionFactory | None

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """Shorthand for ``self.transaction_context.transaction(self.session_factory)``."""
        with self.transaction_context.transaction(self.session_factory) as session:
            yield session

    @contextmanager
    def read_transaction(self) -> Generator[Session, None, None]:
        """
        Shorthand for ``self.transaction_context.read_transaction(self.ro_session_factory)``.

        Raises ``RuntimeError`` if this configuration was built without a read replica
        (``DatabaseAutoConfigurationProperties.build_read_replica=False``).
        """
        if self.ro_session_factory is None:
            raise RuntimeError(
                "read_transaction() requires a read replica — "
                "build with DatabaseAutoConfigurationProperties(build_read_replica=True)"
            )
        with self.transaction_context.read_transaction(self.ro_session_factory) as session:
            yield session


def auto_configure_database(
    settings: DatabaseSettings,
    properties: DatabaseAutoConfigurationProperties | None = None,
) -> DatabaseAutoConfiguration:
    """Build a ``DatabaseAutoConfiguration`` from ``settings``, applying ``properties`` defaults."""
    properties = properties or DatabaseAutoConfigurationProperties()
    return DatabaseAutoConfiguration(
        session_factory=build_session_factory(settings),
        ro_session_factory=build_ro_session_factory(settings) if properties.build_read_replica else None,
        transaction_context=TransactionContext(on_start_transaction=properties.on_start_transaction),
    )
