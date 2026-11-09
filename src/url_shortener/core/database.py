from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from url_shortener.core.settings import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    """Create the app's async engine. No connection is opened until first use."""
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=5,
        pool_pre_ping=True,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the factory that hands out one AsyncSession per unit of work."""
    return async_sessionmaker(engine, expire_on_commit=False)
