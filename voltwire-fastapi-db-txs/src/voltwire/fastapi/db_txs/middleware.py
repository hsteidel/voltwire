"""
FastAPI Transaction Middleware

Provides transparent transaction management for web requests with automatic
commit/rollback behavior, built on top of ``voltwire.db.session.TransactionContext``.

This middleware:
- Opens a read-write session for each HTTP request
- Commits the transaction on successful response (2xx/3xx status codes)
- Rolls back the transaction on exceptions or error status codes
- Always closes the session for proper cleanup
- Works across FastAPI's thread boundaries via the injected ``TransactionContext``

Usage::

    app.add_middleware(
        TransactionMiddleware,
        transaction_context=lambda request: my_transaction_context,
        session_factory=lambda request: my_session_factory,
    )

Both ``transaction_context`` and ``session_factory`` are resolver callables invoked
per request with the ``Request``, not plain instances — this lets apps defer
resolution to whatever they've stashed on ``request.app.state`` (or a DI container),
which matters for apps whose settings/session factories aren't finalized until after
this middleware is constructed (e.g. test harnesses that substitute a test database
via ``request.app.state`` after module import time). Apps with a single fixed
instance for the lifetime of the process can pass ``lambda request: my_instance``.
"""

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from voltwire.fastapi.db_txs.resolvers import SessionFactoryResolver, TransactionContextResolver


class TransactionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that provides transparent transaction management for HTTP requests.

    Automatically manages database session lifecycle:
    - Opens a session before request processing
    - Commits on successful completion (2xx/3xx status codes)
    - Rolls back on exceptions or error status codes
    - Always cleans up resources

    ``transaction_context`` and ``session_factory`` are resolver callables — invoked
    with the current ``Request`` on every request — supplied by the caller. This
    middleware has no knowledge of any DI framework or app-level session registry.
    The resolved ``TransactionContext`` should be the same instance used by any
    read-only dependency built with ``make_read_only_transaction`` and by the app's
    own session-resolution code, since the ContextVars it owns are what tie a
    request's session together across dependencies and route handlers.
    """

    def __init__(
        self,
        app,
        transaction_context: TransactionContextResolver,
        session_factory: SessionFactoryResolver,
    ):
        super().__init__(app)
        self._resolve_transaction_context = transaction_context
        self._resolve_session_factory = session_factory

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle HTTP request with automatic transaction management.

        Opens the RW session eagerly in the async context so that all thread-pool
        workers dispatched by ``call_next`` inherit the same session via context copy.
        Read-only routes shadow it via a dependency built from the same
        ``transaction_context``.
        """
        transaction_context = self._resolve_transaction_context(request)
        session_factory = self._resolve_session_factory(request)

        session = session_factory.get_session()
        transaction_context.set_rw_session(session)
        try:
            response = await call_next(request)

            if 200 <= response.status_code < 399:
                transaction_context.commit()
            else:
                transaction_context.rollback()

            return response

        except Exception:
            transaction_context.rollback()
            raise

        finally:
            transaction_context.close()
