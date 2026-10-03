from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("database")


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


class DatabaseSessionManager:
    """Manages Async SQLAlchemy engine and session factory with automatic fallback."""

    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_maker: async_sessionmaker[AsyncSession] | None = None
        self.is_sqlite_fallback: bool = False

    def init_engine(self, url: str | None = None) -> AsyncEngine:
        target_url = url or settings.DATABASE_URL

        # If already initialized with the same URL, return it
        if self.engine is not None:
            return self.engine

        if "sqlite" in target_url:
            db_file = Path(target_url.replace("sqlite+aiosqlite:///", ""))
            db_file.parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_async_engine(target_url, echo=False)
            self.is_sqlite_fallback = True
        else:
            self.engine = create_async_engine(
                target_url,
                echo=False,
                future=True,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            self.is_sqlite_fallback = False

        self.session_maker = async_sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        return self.engine

    async def initialize(self) -> None:
        """Attempt PostgreSQL initialization, falling back to local SQLite if unreachable."""
        self.init_engine(settings.DATABASE_URL)
        try:
            assert self.engine is not None
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info(
                "Database initialized successfully with primary engine", url=settings.DATABASE_URL
            )
        except Exception as e:
            logger.warning(
                "Primary PostgreSQL database unavailable, falling back to local SQLite",
                error=str(e),
                fallback_url=settings.FALLBACK_SQLITE_URL,
            )
            if self.engine is not None:
                await self.engine.dispose()

            self.engine = None
            self.init_engine(settings.FALLBACK_SQLITE_URL)
            assert self.engine is not None
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Local SQLite metadata engine initialized successfully.")

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self.session_maker = None


db_manager = DatabaseSessionManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    if db_manager.session_maker is None:
        await db_manager.initialize()
    assert db_manager.session_maker is not None
    async with db_manager.session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    await db_manager.initialize()
