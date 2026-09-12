import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from voltwire.db.session import DatabaseSessionFactory, TransactionContext
from voltwire.fastapi.db_txs import TransactionMiddleware


def _build_middleware(transaction_context: TransactionContext, session: MagicMock) -> TransactionMiddleware:
    session_factory = MagicMock(spec=DatabaseSessionFactory)
    session_factory.get_session.return_value = session
    app = MagicMock()
    return TransactionMiddleware(
        app,
        transaction_context=lambda _request: transaction_context,
        session_factory=lambda _request: session_factory,
    )


def _response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    return response


def test_commits_on_success_status():
    context = TransactionContext()
    session = MagicMock()
    middleware = _build_middleware(context, session)
    call_next = AsyncMock(return_value=_response(200))

    result = asyncio.run(middleware.dispatch(MagicMock(), call_next))

    assert result.status_code == 200
    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    session.close.assert_called_once()


def test_rolls_back_on_error_status():
    context = TransactionContext()
    session = MagicMock()
    middleware = _build_middleware(context, session)
    call_next = AsyncMock(return_value=_response(500))

    asyncio.run(middleware.dispatch(MagicMock(), call_next))

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    session.close.assert_called_once()


def test_rolls_back_and_reraises_on_exception():
    context = TransactionContext()
    session = MagicMock()
    middleware = _build_middleware(context, session)
    call_next = AsyncMock(side_effect=ValueError("boom"))

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(middleware.dispatch(MagicMock(), call_next))

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    session.close.assert_called_once()


def test_session_visible_via_transaction_context_during_request():
    context = TransactionContext()
    session = MagicMock()
    middleware = _build_middleware(context, session)

    seen = {}

    async def call_next(_request):
        seen["session"] = context.get_session()
        return _response(200)

    asyncio.run(middleware.dispatch(MagicMock(), call_next))

    assert seen["session"] is session


def test_session_cleared_after_request():
    context = TransactionContext()
    session = MagicMock()
    middleware = _build_middleware(context, session)
    call_next = AsyncMock(return_value=_response(200))

    asyncio.run(middleware.dispatch(MagicMock(), call_next))

    assert context.get_session() is None
