from unittest.mock import MagicMock, patch

import pytest

from voltwire.db.session import DatabaseSettings, SqlAlchemyDatabaseSessionFactory
from voltwire.db.session import default as default_module
from voltwire.db.session.default import (
    configure_database,
    default_database,
    get_transaction_context,
    read_transaction_context,
    transaction_context,
)


def _settings() -> DatabaseSettings:
    return DatabaseSettings(
        host="localhost",
        database="testdb",
        username="user",
        password="pass",
        _env_file=None,
    )


@pytest.fixture(autouse=True)
def _reset_default():
    default_module._default_database = None
    yield
    default_module._default_database = None


class TestBeforeConfiguration:
    def test_default_database_raises_before_configure(self):
        with pytest.raises(RuntimeError):
            default_database()

    def test_get_transaction_context_raises_before_configure(self):
        with pytest.raises(RuntimeError):
            get_transaction_context()


class TestConfigureDefaultDatabase:
    def test_configure_sets_the_default(self):
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            db = configure_database(_settings())

        assert default_database() is db

    def test_reconfigure_replaces_the_default(self):
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            first = configure_database(_settings())
            second = configure_database(_settings())

        assert default_database() is second
        assert first is not second


class TestTransactionContextShorthand:
    def test_transaction_context_commits_via_default_session_factory(self):
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            db = configure_database(_settings())

        session = MagicMock()
        db.session_factory.get_session = MagicMock(return_value=session)

        with transaction_context() as yielded:
            assert yielded is session

        session.commit.assert_called_once()

    def test_read_transaction_context_raises_without_replica(self):
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            configure_database(_settings())

        with pytest.raises(RuntimeError):
            with read_transaction_context():
                pass
