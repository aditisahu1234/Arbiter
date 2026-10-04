from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General Environment
    PROJECT_NAME: str = "Arbiter"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DATA_RAW_DIR: Path = DATA_DIR / "raw"
    DATA_NORMALIZED_DIR: Path = DATA_DIR / "normalized"
    DATA_FACTORS_DIR: Path = DATA_DIR / "factors"
    DATA_QUARANTINE_DIR: Path = DATA_DIR / "quarantine"

    # PostgreSQL OLTP
    DATABASE_URL: str = (
        "postgresql+asyncpg://arbiter_user:arbiter_password@localhost:5432/arbiter_db"
    )
    DATABASE_URL_SYNC: str = "postgresql://arbiter_user:arbiter_password@localhost:5432/arbiter_db"
    # Fallback to local SQLite when PostgreSQL is offline in standalone dev
    FALLBACK_SQLITE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'arbiter_metadata.db'}"
    FALLBACK_SQLITE_SYNC_URL: str = f"sqlite:///{DATA_DIR / 'arbiter_metadata.db'}"

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_DEFAULT_TTL_SECONDS: int = 3600
    ENABLE_CACHE: bool = True

    # DuckDB OLAP
    DUCKDB_PATH: str = str(DATA_DIR / "arbiter_analytics.duckdb")

    # Market Data Provider
    MARKET_DATA_PROVIDER: str = "yahoo"
    YAHOO_REQUEST_DELAY_SECONDS: float = 0.2
    YAHOO_BATCH_SIZE: int = 20

    # Scheduler
    ENABLE_SCHEDULER: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"
    DAILY_INGESTION_CRON_HOUR: int = 16
    DAILY_INGESTION_CRON_MINUTE: int = 0

    # Security & Auth
    SECRET_KEY: str = "arbiter_dev_insecure_secret_key_change_in_production_32bytes_minimum"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
