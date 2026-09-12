"""
Opt-in module-level default configuration.

Everything in ``voltwire.db.session`` takes its ``DatabaseAutoConfiguration``/
``TransactionContext``/``DatabaseSessionFactory`` explicitly — this module is the one
opt-in exception, for callers who want a bare ``with transaction_context():`` without
threading a config object through every call site.

Importing this module does nothing by itself. It only becomes active once your app
calls ``configure_database()`` at startup — until then, ``transaction_context()``/
``read_transaction_context()``/``get_transaction_context()``/``default_database()``
raise ``RuntimeError``.

Usage::

    # app startup, once — configures the database; it autoconfigures in the background
    from voltwire.db.session.default import configure_database
    configure_database(get_db_settings())

    # anywhere else in the app/scripts — no config object to pass around, just
    # get the current default database whenever you need it
    from voltwire.db.session.default import get_transaction_context, transaction_context

    def run():
        with transaction_context():
            user_repo = UserRepository(get_transaction_context().get_session())
            user_repo.save(user)

If your app instantiates more than one ``DatabaseAutoConfiguration`` (e.g. multiple
databases, or multiple FastAPI apps in one process/test session), do not use this
module — hold each ``DatabaseAutoConfiguration`` explicitly instead.
"""

from contextlib import contextmanager
from typing import Generator

from voltwire.db.session.autoconfiguration import (
    DatabaseAutoConfiguration,
    DatabaseAutoConfigurationProperties,
    auto_configure_database,
)
from voltwire.db.session.interfaces import Session
from voltwire.db.session.settings import DatabaseSettings
from voltwire.db.session.transaction import TransactionContext

_default_database: DatabaseAutoConfiguration | None = None


def configure_database(
    settings: DatabaseSettings,
    properties: DatabaseAutoConfigurationProperties | None = None,
) -> DatabaseAutoConfiguration:
    """
    Auto-configure a ``DatabaseAutoConfiguration`` and register it as the process-wide default.

    Call this once at app startup. Calling it again replaces the previous default —
    intended for test setup (e.g. re-pointing at a test database), not routine runtime use.
    """
    global _default_database
    _default_database = auto_configure_database(settings, properties)
    return _default_database


def default_database() -> DatabaseAutoConfiguration:
    """Return the process-wide default ``DatabaseAutoConfiguration``."""
    if _default_database is None:
        raise RuntimeError("configure_database() must be called before using voltwire.db.session.default")
    return _default_database


def get_transaction_context() -> TransactionContext:
    """Return the default configuration's ``TransactionContext``."""
    return default_database().transaction_context


@contextmanager
def transaction_context() -> Generator[Session, None, None]:
    """Shorthand for ``default_database().transaction()``."""
    with default_database().transaction() as session:
        yield session


@contextmanager
def read_transaction_context() -> Generator[Session, None, None]:
    """Shorthand for ``default_database().read_transaction()``."""
    with default_database().read_transaction() as session:
        yield session
