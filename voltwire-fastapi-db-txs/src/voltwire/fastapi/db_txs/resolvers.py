"""
Resolvers

``TransactionMiddleware`` and ``make_read_only_transaction`` depend on resolver
*protocols* — anything callable with ``(request: Request) -> T`` — rather than plain
instances, so resolution can be deferred to whatever the app has stashed on
``request.app.state`` (or elsewhere), instead of requiring a value fixed at wiring
time. A plain function or lambda satisfies the protocol structurally; no subclassing
required::

    TransactionMiddleware(
        app,
        transaction_context=lambda request: my_transaction_context,
        session_factory=lambda request: my_session_factory,
    )

For apps using voltwire-di-core's ``request.app.state.provide(cls)`` convention,
``AppStateResolver`` implements the protocol for you — pass the class you want
resolved::

    TransactionMiddleware(
        app,
        transaction_context=AppStateResolver(TransactionContext),
        session_factory=AppStateResolver(DatabaseSessionFactory),
    )

``AppStateResolver`` is the only piece of this library that assumes anything about
``request.app.state`` beyond FastAPI itself — apps not using that convention should
pass a plain callable instead.
"""

from typing import Generic, Protocol, TypeVar

from voltwire.db.session import DatabaseSessionFactory, RODatabaseSessionFactory, TransactionContext
from starlette.requests import Request

T = TypeVar("T")


class TransactionContextResolver(Protocol):
    def __call__(self, request: Request) -> TransactionContext: ...


class SessionFactoryResolver(Protocol):
    def __call__(self, request: Request) -> DatabaseSessionFactory: ...


class RODatabaseSessionFactoryResolver(Protocol):
    def __call__(self, request: Request) -> RODatabaseSessionFactory: ...


class AppStateResolver(Generic[T]):
    """
    Resolves ``cls`` via ``request.app.state.provide(cls)`` — the voltwire-di-core
    convention for reaching a request's DI container. Satisfies
    ``TransactionContextResolver``/``SessionFactoryResolver``/
    ``RODatabaseSessionFactoryResolver`` for whichever ``cls`` is passed.
    """

    def __init__(self, cls: type[T]) -> None:
        self._cls = cls

    def __call__(self, request: Request) -> T:
        return request.app.state.provide(self._cls)
