"""
Transaction Context Manager for Database Sessions

Provides request/task-scoped transaction management for read-write and read-only
database sessions using contextvars, so the same session is visible across a FastAPI
request's thread-pool workers or across a script/background task's call stack without
threading a ``Session`` through every function signature.

This module is framework-free — callers are responsible for supplying
``DatabaseSessionFactory``/``RODatabaseSessionFactory`` instances explicitly and for
driving commit/rollback/close (e.g. FastAPI middleware) or using the ``transaction()``/
``read_transaction()`` context managers directly for scripts and background tasks.

Usage::

    context = TransactionContext()

    # Explicit transaction control (scripts/background tasks)
    with context.transaction(session_factory):
        user_repo = UserRepository(context.get_session())
        user_repo.save(user)
        # Commits automatically on success, rolls back on exception

    # Read-only replica access (scripts/background tasks)
    with context.read_transaction(ro_session_factory):
        result = repo.find(...)
"""

import contextvars
import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import Generator

from voltwire.db.session.interfaces import DatabaseSessionFactory, RODatabaseSessionFactory, Session

logger = logging.getLogger(__name__)


class TransactionContext:
    """
    Unified, context-aware transaction manager for both read-write and read-only sessions.

    Owns two ContextVars:
    - ``_ro_session_var``: set for the duration of a read-only scope; when present,
      ``get_session()`` returns it and no RW session is ever opened.
    - ``_session_var``: the RW session. For web requests, callers (e.g. middleware) should
      call ``set_rw_session()`` with a pre-created session *before* awaiting downstream
      work in an async context, so thread-pool workers inherit it via the context copy.

    Uses contextvars to work across FastAPI's thread boundaries, unlike threading.local.

    Callers are expected to hold exactly one ``TransactionContext`` instance per process
    and share it between their middleware, dependency wiring, and any script/background-task
    entry points — the ContextVars it owns are what make sessions resolvable across a single
    logical request/task, not the instance itself.
    """

    def __init__(
        self,
        on_start_transaction: Callable[[DatabaseSessionFactory], None] | None = None,
    ) -> None:
        self._session_var: contextvars.ContextVar[Session | None] = contextvars.ContextVar(
            "transaction_session", default=None
        )
        self._ro_session_var: contextvars.ContextVar[Session | None] = contextvars.ContextVar(
            "ro_transaction_session", default=None
        )
        self._on_start_transaction = on_start_transaction

    # ------------------------------------------------------------------
    # Read-only session management
    # ------------------------------------------------------------------

    def set_ro_session(self, session: Session) -> contextvars.Token:
        """Set the read-only replica session for this context. Returns the reset token."""
        return self._ro_session_var.set(session)

    def reset_ro_session(self, token: contextvars.Token) -> None:
        """Reset the read-only session ContextVar to its previous value."""
        self._ro_session_var.reset(token)

    def get_ro_session(self) -> Session | None:
        """Return the active read-only session, or None if not set."""
        return self._ro_session_var.get()

    # ------------------------------------------------------------------
    # Read-write session management
    # ------------------------------------------------------------------

    def set_rw_session(self, session: Session) -> None:
        """
        Store an already-created RW session in ``_session_var`` for this context.

        For web requests, call this *before* awaiting downstream work in an async
        context (e.g. before ``call_next`` in middleware) so the session is set in the
        async event-loop context. Thread-pool workers inherit it via the context copy
        that anyio makes when dispatching sync route handlers.
        """
        self._session_var.set(session)

    def get_session(self) -> Session | None:
        """
        Return the appropriate session for the current context.

        Resolution order:
        1. Read-only replica session (set by ``set_ro_session``/``read_transaction``)
        2. RW session (set by ``set_rw_session``/``start_transaction``)
        3. None if neither has been set
        """
        ro = self._ro_session_var.get()
        if ro:
            return ro
        return self._session_var.get()

    def start_transaction(self, session_factory: DatabaseSessionFactory) -> Session:
        """
        Open a new RW session from ``session_factory`` and store it in ``_session_var``.

        Used by ``transaction()`` for scripts and background tasks. Not required for
        web requests — middleware typically calls ``set_rw_session()`` with a session
        it already created.

        If ``on_start_transaction`` was supplied at construction, it is called with
        ``session_factory`` before the session is opened — e.g. to assert the factory
        is pointed at a test database during a pytest run.
        """
        if self._on_start_transaction is not None:
            self._on_start_transaction(session_factory)
        session = session_factory.get_session()
        self._session_var.set(session)
        logger.debug("RW session %s created for explicit transaction()", id(session))
        return session

    @contextmanager
    def suspend_for_independent_context(self) -> Generator[None, None, None]:
        """
        Temporarily clear both session ContextVars and restore them on exit.

        Used by ``transaction()`` to guarantee a fresh, independent RW session even
        when called from within a scope that already has ``_session_var`` set (e.g. a
        request's RW session) or ``_ro_session_var`` set (a RO scope). On exit both
        ContextVars are restored to their values at the point of entry.
        """
        ro_token = self._ro_session_var.set(None)
        rw_token = self._session_var.set(None)
        try:
            yield
        finally:
            self._ro_session_var.reset(ro_token)
            self._session_var.reset(rw_token)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """Commit the active RW transaction. No-op if no RW session was opened."""
        session = self._session_var.get()
        if session:
            session.commit()

    def rollback(self) -> None:
        """Roll back the active RW transaction. No-op if no RW session was opened."""
        session = self._session_var.get()
        if session:
            session.rollback()

    def close(self) -> None:
        """Close the RW session (if opened) and clear ``_session_var``."""
        session = self._session_var.get()
        if session:
            session.close()
        self._session_var.set(None)

    # ------------------------------------------------------------------
    # Context managers for scripts / background tasks
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(self, session_factory: DatabaseSessionFactory) -> Generator[Session, None, None]:
        """
        Context manager for explicit RW transaction control.

        Automatically handles commit on success, rollback on exception, and cleanup.
        Use this for scripts, background tasks, or any code that needs explicit
        transaction boundaries outside of web-request middleware.

        Guarantees a fresh, independent RW session even if called from within a scope
        that already has a session set (see ``suspend_for_independent_context``).
        """
        with self.suspend_for_independent_context():
            session = self.start_transaction(session_factory)
            try:
                yield session
                self.commit()
            except Exception:
                self.rollback()
                raise
            finally:
                self.close()

    @contextmanager
    def read_transaction(self, ro_session_factory: RODatabaseSessionFactory) -> Generator[Session, None, None]:
        """
        Context manager for read-only replica access in scripts and background tasks.

        Sets the RO session for the duration of the block so that any code resolving a
        session via ``get_session()`` transparently receives the RO session. The
        session is never committed — it is only closed in the finally block.

        For HTTP routes, use a FastAPI dependency built on top of this context instead
        (see the voltwire-fastapi-db-txs package).
        """
        session = ro_session_factory.get_session()
        token = self.set_ro_session(session)
        try:
            yield session
        finally:
            self.reset_ro_session(token)
            session.close()
