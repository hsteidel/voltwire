"""
SQLAlchemy backend

Concrete implementation of :class:`voltwire.db.session.interfaces.DatabaseSessionFactory`
built on SQLAlchemy's engine/connection-pool/``sessionmaker`` machinery. This is the
only module in the package that imports ``sqlalchemy`` — everything else (transaction
management, autoconfiguration, downstream consumers) is written against the
ORM-agnostic interfaces and never needs to know a backend is SQLAlchemy at all.
"""

import logging
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from voltwire.db.session.settings import DatabaseSettings

logger = logging.getLogger(__name__)


class SqlAlchemyDatabaseSessionFactory:
    """Configured SQLAlchemy session factory backed by a connection pool.

    Prefer :func:`build_session_factory` over constructing this directly.
    Callers are responsible for managing the lifecycle of sessions returned
    by :meth:`get_session`. Call :meth:`close` on shutdown to release pool connections.

    Example::

        settings = DatabaseSettings.from_env(".env")
        factory = build_session_factory(settings)

        session = factory.get_session()
        try:
            # use session
            session.commit()
        finally:
            session.close()

        # On app shutdown
        factory.close()
    """

    def __init__(
        self,
        url: str,
        schema_name: str,
        engine_kwargs: dict[str, Any] | None = None,
        connect_args: dict[str, Any] | None = None,
    ):
        self._schema_name: str = schema_name
        engine = create_engine(
            url,
            **(engine_kwargs or {}),
            execution_options={"schema_translate_map": {None: schema_name}, **self._extra_execution_options()},
            connect_args=connect_args or {},
        )
        self._engine: Engine | None = engine
        self._setup_pool_listeners(engine)
        self._session_maker: sessionmaker | None = sessionmaker(autocommit=False, bind=engine, expire_on_commit=False)
        logger.debug("DB Engine created successfully.")

    def _setup_pool_listeners(self, engine: Engine) -> None:
        @event.listens_for(engine.pool, "reset")
        def receive_reset(dbapi_conn, connection_record, reset_state):
            if reset_state.terminate_only:
                return
            try:
                if hasattr(dbapi_conn, "rollback"):
                    dbapi_conn.rollback()
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ["ssl", "connection", "closed", "terminated", "broken"]):
                    logger.warning(
                        "Connection reset failed with network error (stale connection), invalidating: %s",
                        e,
                        exc_info=False,
                    )
                    connection_record.invalidate(e)
                else:
                    logger.error("Unexpected error during connection reset: %s", e, exc_info=True)
                    raise

        @event.listens_for(engine.pool, "connect")
        def receive_connect(dbapi_conn, connection_record):
            logger.debug("New database connection established: %s", id(dbapi_conn))

        @event.listens_for(engine.pool, "close")
        def receive_close(dbapi_conn, connection_record):
            try:
                if hasattr(dbapi_conn, "close"):
                    dbapi_conn.close()
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ["ssl", "connection", "closed", "terminated"]):
                    logger.warning(
                        "Connection close failed with network error (expected for dead connections): %s",
                        e,
                        exc_info=False,
                    )
                else:
                    logger.error("Unexpected error closing connection: %s", e, exc_info=True)

    def close(self) -> None:
        if self._engine is None:
            logger.warning("no engine to dispose")
            return
        logger.debug("closing engine")
        self._engine.dispose()
        self._engine = None
        self._session_maker = None

    def _extra_execution_options(self) -> dict:
        return {}

    def get_session(self) -> Session:
        if self._session_maker is None:
            raise RuntimeError("SqlAlchemyDatabaseSessionFactory has been closed")
        return self._session_maker()

    def get_engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("SqlAlchemyDatabaseSessionFactory has been closed")
        return self._engine

    @staticmethod
    def from_settings(
        db_settings: DatabaseSettings, engine_kwargs: dict[str, Any] | None = None
    ) -> "SqlAlchemyDatabaseSessionFactory":
        logger.info("Creating session factory for database at %s", db_settings.get_primary_db_url())
        if engine_kwargs is None:
            engine_kwargs = {}
        return SqlAlchemyDatabaseSessionFactory(
            url=db_settings.get_primary_db_url(),
            schema_name=db_settings.schema_name,
            engine_kwargs=engine_kwargs,
        )


class SqlAlchemyRODatabaseSessionFactory(SqlAlchemyDatabaseSessionFactory):
    """Read-only session factory targeting a replica.

    Enforces read-only at the DB layer via ``postgresql_readonly=True``, so writes
    are rejected by PostgreSQL even when the RO host falls back to the primary writer.
    Use :func:`build_ro_session_factory` to construct.
    """

    def _extra_execution_options(self) -> dict:
        return {"postgresql_readonly": True}


def build_session_factory(db_settings: DatabaseSettings) -> SqlAlchemyDatabaseSessionFactory:
    """Build a :class:`SqlAlchemyDatabaseSessionFactory` from :class:`~voltwire.db.session.DatabaseSettings`.

    Applies full pool configuration and connection args from the settings object.
    """
    logger.debug("Creating SqlAlchemyDatabaseSessionFactory for %s", db_settings.get_connection_debug_string())
    return SqlAlchemyDatabaseSessionFactory(
        db_settings.get_primary_db_url(),
        db_settings.schema_name,
        engine_kwargs=db_settings.get_engine_kwargs(),
        connect_args=db_settings.get_connect_args(),
    )


def build_ro_session_factory(db_settings: DatabaseSettings) -> SqlAlchemyRODatabaseSessionFactory:
    """Build a :class:`SqlAlchemyRODatabaseSessionFactory` pointing at the read-only replica.

    Falls back to the primary host if ``DB_RO_HOST`` is not set.
    """
    logger.debug("Creating SqlAlchemyRODatabaseSessionFactory for %s", db_settings.get_connection_debug_string())
    return SqlAlchemyRODatabaseSessionFactory(
        db_settings.get_readonly_db_url(),
        db_settings.schema_name,
        engine_kwargs=db_settings.get_engine_kwargs(),
        connect_args=db_settings.get_readonly_connect_args(),
    )
