from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Lazy init — engine is only created on first real request, not at import time.
# This lets tests override get_db without triggering a connection attempt.
_engine = None
_session_factory = None


def _get_session_factory():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url.get_secret_value(), echo=settings.debug
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _get_session_factory()() as session:
        yield session
