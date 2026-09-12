import asyncio
from unittest.mock import MagicMock

from voltwire.db.session import RODatabaseSessionFactory, TransactionContext
from voltwire.fastapi.db_txs import make_read_only_transaction


def _ro_factory(session: MagicMock) -> MagicMock:
    factory = MagicMock(spec=RODatabaseSessionFactory)
    factory.get_session.return_value = session
    return factory


async def _drain(dependency) -> None:
    """Fully exercise a FastAPI Depends()-wrapped async generator, like FastAPI would."""
    agen = dependency.dependency(MagicMock())
    await agen.__anext__()
    try:
        await agen.__anext__()
    except StopAsyncIteration:
        pass


def test_ro_session_active_during_yield():
    context = TransactionContext()
    session = MagicMock()
    ro_transaction = make_read_only_transaction(lambda _request: _ro_factory(session), lambda _request: context)

    seen = {}

    async def run():
        agen = ro_transaction.dependency(MagicMock())
        await agen.__anext__()
        seen["session"] = context.get_session()
        try:
            await agen.__anext__()
        except StopAsyncIteration:
            pass

    asyncio.run(run())

    assert seen["session"] is session


def test_session_closed_and_context_cleared_after():
    context = TransactionContext()
    session = MagicMock()
    ro_transaction = make_read_only_transaction(lambda _request: _ro_factory(session), lambda _request: context)

    asyncio.run(_drain(ro_transaction))

    session.close.assert_called_once()
    assert context.get_ro_session() is None


def test_never_commits():
    context = TransactionContext()
    session = MagicMock()
    ro_transaction = make_read_only_transaction(lambda _request: _ro_factory(session), lambda _request: context)

    asyncio.run(_drain(ro_transaction))

    session.commit.assert_not_called()


def test_restores_previous_ro_session_after_completion():
    context = TransactionContext()
    outer_session = MagicMock()
    context.set_ro_session(outer_session)

    inner_session = MagicMock()
    ro_transaction = make_read_only_transaction(lambda _request: _ro_factory(inner_session), lambda _request: context)

    asyncio.run(_drain(ro_transaction))

    assert context.get_ro_session() is outer_session
