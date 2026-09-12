<img src="https://raw.githubusercontent.com/hsteidel/voltwire/main/assets/icons/fastapi-db-txs.svg" alt="" width="56" height="56" align="left">

# voltwire-fastapi-db-txs

FastAPI integration for `voltwire.db.session.TransactionContext` (from
[voltwire-db-session](https://pypi.org/project/voltwire-db-session/)): request-scoped read-write and
read-only database sessions with automatic commit/rollback, so route handlers never manage
session lifecycle themselves.

**No hidden global state, no DI framework coupling.** Every component here depends on
*resolvers* — anything callable as `(request: Request) -> T` — for `TransactionContext`
and the relevant session factory, rather than plain instances. This lets apps defer
resolution to `request.app.state`, a DI container, or anywhere else, which matters for
apps whose DB config isn't finalized until after this middleware/dependency is
constructed (e.g. test harnesses that substitute a test database after module import
time). Apps with one fixed instance for the process's lifetime just pass
`lambda request: my_instance`.

## Installation

```bash
pip install voltwire-fastapi-db-txs
# or with Poetry:
poetry add voltwire-fastapi-db-txs
```

## Wiring it into your app

Your app should hold exactly one `TransactionContext` instance for the life of the process.
The easiest way to get one — along with its matching `DatabaseSessionFactory`/
`RODatabaseSessionFactory` — is `auto_configure_database`, from voltwire-db-session. If your DB
config is ready before any route module gets imported, resolve it once and close over it:

```python
from voltwire.db.session import auto_configure_database, DatabaseAutoConfigurationProperties
from voltwire.fastapi.db_txs import TransactionMiddleware, make_read_only_transaction

db = auto_configure_database(db_settings, DatabaseAutoConfigurationProperties(build_read_replica=True))

app.add_middleware(
    TransactionMiddleware,
    transaction_context=lambda request: db.transaction_context,
    session_factory=lambda request: db.session_factory,
)

ReadOnlyTransaction = make_read_only_transaction(
    lambda request: db.ro_session_factory,
    lambda request: db.transaction_context,
)
```

If your app defers DB config until later (e.g. it's set on `request.app.state` during
startup, or substituted for a test database after these components are constructed),
resolve from the request instead. If your app uses voltwire-di-core's
`request.app.state.provide(cls)` convention, `AppStateResolver` implements the resolver
protocol for you — pass the class you want resolved:

```python
from voltwire.fastapi.db_txs import AppStateResolver

app.add_middleware(
    TransactionMiddleware,
    transaction_context=AppStateResolver(TransactionContext),
    session_factory=AppStateResolver(DatabaseSessionFactory),
)

ReadOnlyTransaction = make_read_only_transaction(
    AppStateResolver(RODatabaseSessionFactory),
    AppStateResolver(TransactionContext),
)
```

Apps not using that convention can pass any other callable of the same shape —
`lambda request: request.app.state.my_custom_lookup(TransactionContext)`, a bound
method, or a small resolver class of their own.

If you'd rather assemble the session factories yourself (e.g. a custom
`DatabaseSessionFactory` subclass) instead of using `auto_configure_database`, build each
one directly — `TransactionMiddleware` and `make_read_only_transaction` only need
resolvers returning a `TransactionContext` and the relevant factory, however you got them:

```python
from voltwire.db.session import TransactionContext, build_session_factory, build_ro_session_factory

transaction_context = TransactionContext()
session_factory = build_session_factory(db_settings)
ro_session_factory = build_ro_session_factory(db_settings)
```

## Using it in routes

Write routes (RW by default — the middleware opens a session for every request):

```python
@router.post("/users")
def create_user(user_repo: UserRepositoryDI):
    return user_repo.save(user)  # commits automatically on a 2xx/3xx response
```

Read-only routes (route or router-level, targets your read replica instead):

```python
@router.get("/users", dependencies=[ReadOnlyTransaction])
def search_users(user_repo: UserRepositoryDI) -> list[UserResponse]:
    ...
```

Wherever your app resolves a `Session` for its repositories, call
`transaction_context.get_session()` — it returns the RO session if one is active for the
current request, otherwise the RW session opened by the middleware, otherwise `None`.

## Scripts and background tasks

For code outside a FastAPI request (management scripts, workers), use the context managers
directly instead of the middleware/dependency — either via the `db` object from
`auto_configure_database`:

```python
with db.transaction():
    user_repo = UserRepository(db.transaction_context.get_session())
    user_repo.save(user)
    # commits on success, rolls back on exception

with db.read_transaction():
    result = repo.find(...)
```

or, if you built the pieces yourself, the same methods on `TransactionContext` directly:

```python
with transaction_context.transaction(session_factory):
    user_repo = UserRepository(transaction_context.get_session())
    user_repo.save(user)

with transaction_context.read_transaction(ro_session_factory):
    result = repo.find(...)
```

If a single `DatabaseAutoConfiguration` is truly the only one in the process (no multiple
databases, no multiple apps sharing the interpreter — e.g. in a pytest session), voltwire-db-session
also has an opt-in `voltwire.db.session.default` module for a bare `with transaction():` — see
voltwire-db-session's docs for when that tradeoff is worth it.

## Why resolvers instead of instances?

This library has no knowledge of any dependency-injection framework — `TransactionMiddleware`
and `make_read_only_transaction` never construct or own a `TransactionContext`/session
factory themselves. Depending on a resolver *protocol* instead of a plain instance means
your app decides *when* resolution happens: eagerly (a lambda that just returns a value
captured at wiring time) or lazily per request (e.g. `request.app.state.provide(...)`),
without this library needing to know which. `AppStateResolver` is the one piece that
assumes anything about `request.app.state` beyond FastAPI itself — it exists purely as a
convenience for voltwire-di-core's convention; everything else in this library only ever calls
the resolver, never reaches into `request.app.state` directly. The one thing that
matters regardless of which resolver you use: share the *same* `TransactionContext`
instance across the middleware, any read-only dependencies, and your app's own
session-resolution code — its ContextVars are what tie a request's session together.
