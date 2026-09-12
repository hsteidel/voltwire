from unittest.mock import MagicMock

from voltwire.db.session import TransactionContext
from voltwire.fastapi.db_txs import AppStateResolver


class TestAppStateResolver:
    def test_calls_provide_with_the_given_class(self):
        resolved = TransactionContext()
        request = MagicMock()
        request.app.state.provide.return_value = resolved

        resolver = AppStateResolver(TransactionContext)
        result = resolver(request)

        request.app.state.provide.assert_called_once_with(TransactionContext)
        assert result is resolved

    def test_re_resolves_on_every_call(self):
        request = MagicMock()
        resolver = AppStateResolver(TransactionContext)

        resolver(request)
        resolver(request)

        assert request.app.state.provide.call_count == 2
