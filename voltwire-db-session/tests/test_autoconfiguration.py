from unittest.mock import MagicMock, patch

import pytest

from voltwire.db.session import (
    DatabaseAutoConfigurationProperties,
    DatabaseSessionFactory,
    DatabaseSettings,
    RODatabaseSessionFactory,
    SqlAlchemyDatabaseSessionFactory,
    SqlAlchemyRODatabaseSessionFactory,
    TransactionContext,
    auto_configure_database,
)


def _settings() -> DatabaseSettings:
    return DatabaseSettings(
        host="localhost",
        database="testdb",
        username="user",
        password="pass",
        _env_file=None,
    )


def _patched_create_engine():
    return patch("voltwire.db.session.backends.sqlalchemy.create_engine")


class TestConfigureDatabase:
    def test_skips_read_replica_by_default(self):
        with _patched_create_engine() as mock_ce, patch.object(SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            db = auto_configure_database(_settings())

        assert isinstance(db.session_factory, DatabaseSessionFactory)
        assert isinstance(db.transaction_context, TransactionContext)
        assert db.ro_session_factory is None

    def test_builds_read_replica_when_enabled(self):
        properties = DatabaseAutoConfigurationProperties(build_read_replica=True)
        with _patched_create_engine() as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ), patch.object(SqlAlchemyRODatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            db = auto_configure_database(_settings(), properties)

        assert isinstance(db.ro_session_factory, RODatabaseSessionFactory)

    def test_each_call_returns_a_fresh_transaction_context(self):
        with _patched_create_engine() as mock_ce, patch.object(SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            first = auto_configure_database(_settings())
            second = auto_configure_database(_settings())

        assert first.transaction_context is not second.transaction_context

    def test_on_start_transaction_property_wired_into_transaction_context(self):
        seen = []
        properties = DatabaseAutoConfigurationProperties(on_start_transaction=seen.append)
        with _patched_create_engine() as mock_ce, patch.object(SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            db = auto_configure_database(_settings(), properties)

        db.transaction_context.start_transaction(db.session_factory)

        assert seen == [db.session_factory]


class TestAutoConfigurationTransactionShorthand:
    def test_transaction_delegates_to_context_and_session_factory(self):
        with _patched_create_engine() as mock_ce, patch.object(SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            db = auto_configure_database(_settings())

        session = MagicMock()
        db.session_factory.get_session = MagicMock(return_value=session)

        with db.transaction() as yielded:
            assert yielded is session
            assert db.transaction_context.get_session() is session

        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_read_transaction_raises_without_replica(self):
        with _patched_create_engine() as mock_ce, patch.object(SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            db = auto_configure_database(_settings())

        with pytest.raises(RuntimeError):
            with db.read_transaction():
                pass

    def test_read_transaction_delegates_to_ro_factory_when_present(self):
        properties = DatabaseAutoConfigurationProperties(build_read_replica=True)
        with _patched_create_engine() as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ), patch.object(SqlAlchemyRODatabaseSessionFactory, "_setup_pool_listeners"):
            mock_ce.return_value = MagicMock()
            db = auto_configure_database(_settings(), properties)

        session = MagicMock()
        db.ro_session_factory.get_session = MagicMock(return_value=session)

        with db.read_transaction() as yielded:
            assert yielded is session

        session.commit.assert_not_called()
        session.close.assert_called_once()
