"""SQLAlchemy async session management."""

import os
import socket
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from libs.common.config import settings

_engine: AsyncEngine | None = None
_session_factory = None


async def init_db():
    """Ensure database tables and columns are initialized."""
    engine = get_engine()
    from libs.common.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE runs ADD COLUMN user_id VARCHAR(36)"))
        except Exception:
            pass


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        db_url = settings.DATABASE_URL
        if "postgres" in db_url:
            is_postgres_available = False
            try:
                parsed = urlparse(db_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 5432
                socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
                is_postgres_available = True
            except Exception:
                is_postgres_available = False

            if not is_postgres_available:
                os.makedirs("./data", exist_ok=True)
                db_url = "sqlite+aiosqlite:///./data/eia_service.db"

        if "sqlite" in db_url:
            _engine = create_async_engine(db_url, echo=False)
        else:
            _engine = create_async_engine(
                db_url,
                echo=(settings.ENVIRONMENT == "development" and settings.LOG_LEVEL == "DEBUG"),
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async transactional database session context."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Close engine connection pool."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
