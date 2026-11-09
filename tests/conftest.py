import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from url_shortener.app import create_app
from url_shortener.core.settings import Settings
from url_shortener.deps.database import get_db_session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://shortener:shortener@localhost:5432/shortener_test",
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """URL of the database the test suite runs against."""
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def alembic_config(test_database_url: str) -> Config:
    """Alembic configuration aimed at the test database."""
    config = Config(toml_file=str(PROJECT_ROOT / "pyproject.toml"))
    config.set_main_option("sqlalchemy.url", test_database_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def migrated_database(alembic_config: Config) -> None:
    """Rebuild the test database schema once per test run."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


@pytest.fixture
def test_settings() -> Settings:
    """Create a Settings instance for testing purposes."""
    return Settings(
        _env_file=None,
        env="test",
        database_url=SecretStr(TEST_DATABASE_URL),
        cleanup_secret=SecretStr("test-secret"),
    )


@pytest.fixture
async def db_session(migrated_database: None) -> AsyncIterator[AsyncSession]:
    """Provide a session inside a transaction that is rolled back after the test."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def client(test_settings: Settings, db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Create an async test client for the FastAPI app."""
    app = create_app(test_settings)

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
