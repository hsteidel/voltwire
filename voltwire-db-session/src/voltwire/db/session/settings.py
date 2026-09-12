from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings, loaded from environment variables with a ``DB_`` prefix.

    By default reads from a ``.env`` file in the working directory. Use :meth:`from_env` to
    specify a different file (e.g. ``.env.local``), or pass ``_env_file=None`` to skip file
    loading and rely purely on environment variables or keyword arguments.

    Example::

        # Standard .env
        settings = DatabaseSettings()

        # Custom env file
        settings = DatabaseSettings.from_env(".env.local")

        # No file — values from env vars or kwargs only
        settings = DatabaseSettings.from_env(None)
        settings = DatabaseSettings(host="localhost", database="mydb", _env_file=None)
    """

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="postgres")
    username: str = Field(default="postgres")
    password: str = Field(default="postgres")
    schema_name: str = Field(default="public")
    driver: str = Field(default="psycopg2", description="SQLAlchemy driver name (e.g. psycopg2, psycopg, asyncpg)")
    pool_size: int = Field(default=10, description="Minimum connections in pool")
    max_pool_size: int = Field(default=20, description="Maximum number of allowed connections")
    pool_timeout: int = Field(default=30, description="Seconds to wait for a connection from pool")
    pool_recycle: int = Field(default=299, description="Recycle connections after this many seconds")
    pool_reset_on_return: str = Field(
        default="rollback", description="How to reset connections on return: rollback, commit, or None"
    )
    tcp_keepalives_idle: int = Field(default=60, description="Seconds between TCP keepalive probes")
    tcp_keepalives_interval: int = Field(default=60, description="Seconds between TCP keepalive retransmissions")
    tcp_keepalives_count: int = Field(default=3, description="Number of TCP keepalive probes")
    application_name: str = Field(default="app", description="Application name for database connections")

    ro_host: str | None = Field(
        default=None,
        description="Read-only replica host. Falls back to primary host if not set.",
    )
    ro_statement_timeout_ms: int = Field(
        default=30_000,
        description="Time to kill a statement that has been running longer than this (in milliseconds)",
    )

    model_config = SettingsConfigDict(extra="ignore", env_file=".env", env_prefix="DB_")

    @classmethod
    def from_env(cls, env_file: str | None = ".env", **kwargs) -> "DatabaseSettings":
        """Create settings from a specific env file path.

        Args:
            env_file: Path to the ``.env`` file. Pass ``None`` to skip file loading
                      and rely purely on environment variables or ``kwargs``.
            **kwargs: Override any field directly, e.g. ``host="localhost"``.

        Examples::

            DatabaseSettings.from_env(".env.local")
            DatabaseSettings.from_env(None, host="localhost", database="mydb")
        """
        return cls(_env_file=env_file, **kwargs)

    def get_primary_db_url(self) -> str:
        return self._get_db_url(self.host)

    def get_readonly_db_url(self) -> str:
        return self._get_db_url(self.ro_host or self.host)

    def _get_db_url(self, target_host: str) -> str:
        return f"postgresql+{self.driver}://{self.username}:{self.password}@{target_host}:{self.port}/{self.database}"

    def get_connection_debug_string(self) -> str:
        return f"Host: {self.host} Port: {self.port} Database: {self.database} Schema: {self.schema_name}"

    def get_pool_size_overflow(self) -> int:
        return self.max_pool_size - self.pool_size

    def get_engine_kwargs(self) -> dict:
        return {
            "pool_pre_ping": True,
            "pool_size": self.pool_size,
            "max_overflow": self.get_pool_size_overflow(),
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_reset_on_return": self.pool_reset_on_return,
        }

    def get_connect_args(self) -> dict:
        return {
            "keepalives_idle": self.tcp_keepalives_idle,
            "keepalives_interval": self.tcp_keepalives_interval,
            "keepalives_count": self.tcp_keepalives_count,
            "application_name": self.application_name,
            "options": f"-c search_path={self.schema_name} -c timezone=UTC",
        }

    def get_readonly_connect_args(self) -> dict:
        connect_args = self.get_connect_args()
        connect_args["options"] += f" -c statement_timeout={self.ro_statement_timeout_ms}"
        return connect_args
