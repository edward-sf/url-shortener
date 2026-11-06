from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from url_shortener.app import create_app
from url_shortener.core.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Create a Settings instance for testing purposes."""
    return Settings(
        _env_file=None,
        env="test",
        database_url=SecretStr("postgresql+asyncpg://test:test@localhost:5432/test"),
        cleanup_secret=SecretStr("test-secret"),
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncIterator[AsyncClient]:
    """Create an async test client for the FastAPI app."""
    app = create_app(test_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
