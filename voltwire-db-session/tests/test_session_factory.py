from unittest.mock import MagicMock, patch

import pytest

from voltwire.db.session import (
    DatabaseSessionFactory,
    DatabaseSettings,
    RODatabaseSessionFactory,
    SqlAlchemyDatabaseSessionFactory,
    SqlAlchemyRODatabaseSessionFactory,
    build_ro_session_factory,
    build_session_factory,
)


class TestDatabaseSettings:
    def test_default_url_uses_psycopg2(self):
        settings = DatabaseSettings(
            host="db-host",
            port=5432,
            database="mydb",
            username="user",
            password="pass",
            _env_file=None,
        )
        assert settings.get_primary_db_url() == "postgresql+psycopg2://user:pass@db-host:5432/mydb"

    def test_driver_field_changes_url_scheme(self):
        settings = DatabaseSettings(
            host="db-host",
            driver="psycopg",
            database="mydb",
            username="user",
            password="pass",
            _env_file=None,
        )
        assert "postgresql+psycopg://" in settings.get_primary_db_url()

    def test_readonly_url_falls_back_to_primary_host(self):
        settings = DatabaseSettings(
            host="primary",
            ro_host=None,
            database="mydb",
            username="user",
            password="pass",
            _env_file=None,
        )
        assert "primary" in settings.get_readonly_db_url()

    def test_readonly_url_uses_ro_host_when_set(self):
        settings = DatabaseSettings(
            host="primary",
            ro_host="replica",
            database="mydb",
            username="user",
            password="pass",
            _env_file=None,
        )
        assert "replica" in settings.get_readonly_db_url()

    def test_get_engine_kwargs_returns_expected_keys(self):
        settings = DatabaseSettings(_env_file=None)
        kwargs = settings.get_engine_kwargs()
        assert "pool_pre_ping" in kwargs
        assert "pool_size" in kwargs
        assert "max_overflow" in kwargs
        assert "pool_timeout" in kwargs
        assert "pool_recycle" in kwargs

    def test_max_overflow_derived_from_pool_sizes(self):
        settings = DatabaseSettings(pool_size=5, max_pool_size=15, _env_file=None)
        assert settings.get_engine_kwargs()["max_overflow"] == 10

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "env-host")
        monkeypatch.setenv("DB_DATABASE", "env-db")
        settings = DatabaseSettings(_env_file=None)
        assert settings.host == "env-host"
        assert settings.database == "env-db"

    def test_env_file_override_with_none_skips_file(self):
        # Should not raise even when no .env file exists
        settings = DatabaseSettings(_env_file=None)
        assert settings is not None

    def test_readonly_connect_args_appends_statement_timeout(self):
        settings = DatabaseSettings(ro_statement_timeout_ms=15_000, _env_file=None)
        connect_args = settings.get_readonly_connect_args()
        assert connect_args["options"].endswith("-c statement_timeout=15000")

    def test_connect_args_has_no_statement_timeout(self):
        settings = DatabaseSettings(_env_file=None)
        assert "statement_timeout" not in settings.get_connect_args()["options"]


class TestSqlAlchemyDatabaseSessionFactory:
    def test_raises_on_invalid_url(self):
        # SQLAlchemy raises ArgumentError for completely invalid URLs
        from sqlalchemy.exc import ArgumentError

        with pytest.raises((ArgumentError, Exception)):
            SqlAlchemyDatabaseSessionFactory(url="not-a-url", schema_name="public")

    def _make_factory(self, **kwargs) -> SqlAlchemyDatabaseSessionFactory:
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            return SqlAlchemyDatabaseSessionFactory(url="postgresql+psycopg2://u:p@h/db", schema_name="public", **kwargs)

    def test_get_session_raises_after_close(self):
        factory = self._make_factory()
        factory.close()
        with pytest.raises(RuntimeError, match="closed"):
            factory.get_session()

    def test_get_engine_raises_after_close(self):
        factory = self._make_factory()
        factory.close()
        with pytest.raises(RuntimeError, match="closed"):
            factory.get_engine()

    def test_satisfies_database_session_factory_interface(self):
        factory = self._make_factory()
        assert isinstance(factory, DatabaseSessionFactory)

    def test_build_session_factory_creates_instance(self):
        settings = DatabaseSettings(
            host="localhost",
            database="testdb",
            username="user",
            password="pass",
            _env_file=None,
        )
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyDatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            factory = build_session_factory(settings)
        assert isinstance(factory, SqlAlchemyDatabaseSessionFactory)
        assert isinstance(factory, DatabaseSessionFactory)

    def test_build_ro_session_factory_creates_ro_instance(self):
        settings = DatabaseSettings(
            host="localhost",
            database="testdb",
            username="user",
            password="pass",
            _env_file=None,
        )
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyRODatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            factory = build_ro_session_factory(settings)
        assert isinstance(factory, SqlAlchemyRODatabaseSessionFactory)
        assert isinstance(factory, RODatabaseSessionFactory)

    def test_build_ro_session_factory_applies_statement_timeout(self):
        settings = DatabaseSettings(
            host="localhost",
            database="testdb",
            username="user",
            password="pass",
            ro_statement_timeout_ms=15_000,
            _env_file=None,
        )
        with patch("voltwire.db.session.backends.sqlalchemy.create_engine") as mock_ce, patch.object(
            SqlAlchemyRODatabaseSessionFactory, "_setup_pool_listeners"
        ):
            mock_ce.return_value = MagicMock()
            build_ro_session_factory(settings)
        connect_args = mock_ce.call_args.kwargs["connect_args"]
        assert connect_args["options"].endswith("-c statement_timeout=15000")

    def test_ro_factory_extra_execution_options(self):
        factory = SqlAlchemyRODatabaseSessionFactory.__new__(SqlAlchemyRODatabaseSessionFactory)
        assert factory._extra_execution_options() == {"postgresql_readonly": True}

    def test_base_factory_extra_execution_options_empty(self):
        factory = SqlAlchemyDatabaseSessionFactory.__new__(SqlAlchemyDatabaseSessionFactory)
        assert factory._extra_execution_options() == {}
