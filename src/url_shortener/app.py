from contextlib import asynccontextmanager

from fastapi import FastAPI

from url_shortener.api.health import router as health_router
from url_shortener.core.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a FastAPI app with the given settings, or default settings if none are provided."""
    if settings is None:
        settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Task 2: build the async DB engine + session maker, store on app.state
        yield
        # Task 2: dispose of the engine

    app = FastAPI(title="URL Shortener", lifespan=lifespan)

    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings

    register_routers(app)
    # register_error_handlers(app)          # Task 7: the error envelope
    # register_rate_limiter(app, settings)  # Task 7

    return app


def register_routers(app: FastAPI) -> None:
    """Register routers with the FastAPI app.

    Args:
        app (FastAPI): The FastAPI application instance to register routers with.
    Returns:
        None
    """
    app.include_router(health_router)
