from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from url_shortener.app import create_app
from url_shortener.core.errors import AppError
from url_shortener.core.settings import Settings


class TeapotError(AppError):
    status_code = 418
    code = "teapot"
    default_message = "I'm a teapot."


class Payload(BaseModel):
    url: str


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    """The real app, plus throwaway routes that trigger each kind of error."""
    app = create_app(test_settings)

    @app.get("/_test/teapot")
    async def teapot() -> None:
        raise TeapotError(field="kettle")

    @app.post("/_test/payload")
    async def payload(body: Payload) -> None:
        return None

    @app.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError("password=hunter2")

    return app


@pytest.fixture
async def error_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def test_app_error_uses_envelope(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/teapot")

    assert response.status_code == 418
    assert response.json() == {
        "error": {"code": "teapot", "message": "I'm a teapot.", "field": "kettle"}
    }


async def test_validation_error_uses_evelope_with_details(error_client: AsyncClient) -> None:
    response = await error_client.post("/_test/payload", json={})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "The request is invalid.",
            "details": [{"field": "url", "message": "Field required"}],
        }
    }


async def test_validation_error_does_not_echo_input(error_client: AsyncClient) -> None:
    response = await error_client.post("/_test/payload", json={"url": ["sk_secret"]})

    assert response.status_code == 422
    assert "sk_secret" not in response.text


async def test_malformed_json_points_at_body(error_client: AsyncClient) -> None:
    response = await error_client.post(
        "/_test/payload",
        content=b"{malformed json string",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "body", "message": "JSON decode error"}
    ]


async def test_unknown_route_uses_envelope(error_client: AsyncClient) -> None:
    response = await error_client.post("/does_not_exist", json={"url": ["sk_secret"]})

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


async def test_wrong_method_uses_envelope(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/payload")

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert response.json() == {
        "error": {"code": "method_not_allowed", "message": "Method Not Allowed"}
    }


async def test_unexpected_error_hides_details(error_client: AsyncClient) -> None:
    response = await error_client.get("/_test/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong."}
    }
