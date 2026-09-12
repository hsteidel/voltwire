"""
Read-Replica FastAPI Dependency Builder

FastAPI's ``Depends()`` callables can't take extra constructor arguments, so the
read-only dependency is produced by a builder function instead: call
``make_read_only_transaction`` once at app-wiring time with resolver callables for
your ``RODatabaseSessionFactory`` and the same ``TransactionContext`` instance used by
``TransactionMiddleware``, then bind the result to a name in your app::

    ReadOnlyTransaction = make_read_only_transaction(
        lambda request: my_ro_session_factory,
        lambda request: my_transaction_context,
    )

    @router.get("", dependencies=[ReadOnlyTransaction])
    def search_items(service: MyServiceDI) -> MySearchResponse:
        ...

Both resolvers are invoked per request with the ``Request`` rather than passed as
plain instances — this lets apps defer resolution to whatever they've stashed on
``request.app.state`` (or a DI container), which matters for apps whose settings/
session factories aren't finalized until after this dependency is built (e.g. test
harnesses that substitute a test database via ``request.app.state`` after module
import time). Apps with a single fixed instance for the lifetime of the process can
pass ``lambda request: my_instance``.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.params import Depends as DependsType

from voltwire.fastapi.db_txs.resolvers import RODatabaseSessionFactoryResolver, TransactionContextResolver


def make_read_only_transaction(
    ro_session_factory: RODatabaseSessionFactoryResolver,
    transaction_context: TransactionContextResolver,
) -> DependsType:
    """
    Build a FastAPI dependency that opens a read-only replica session for the
    duration of a request.

    Keeps the RO session open for the full duration of the request so that all
    downstream session resolution within the route uses the replica.

    Must be async so the ContextVar is set and reset within the async event-loop
    context — mirroring ``TransactionMiddleware``. Sync generator dependencies run in
    a thread pool where anyio snapshots the context, causing ContextVar tokens to be
    bound to the thread's copied Context; the token would then be invalid when FastAPI
    runs generator cleanup in a different context snapshot. As an async generator,
    ``set()``/``reset()`` both execute in the same async Context, and the sync route
    thread inherits the session via the context copy.
    """

    async def build_read_replica_context(request: Request) -> AsyncGenerator[None, None]:
        session = ro_session_factory(request).get_session()
        context = transaction_context(request)
        token = context.set_ro_session(session)
        try:
            yield
        finally:
            context.reset_ro_session(token)
            session.close()

    return Depends(build_read_replica_context)
