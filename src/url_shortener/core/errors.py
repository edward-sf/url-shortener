from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_LOCATION_SOURCES = frozenset({"body", "query", "path", "header", "cookie"})


class AppError(Exception):
    """An expected error that the API turns into the error envelope.

    Subclasses set ``status_code``, ``code`` and ``default_message``.
    """

    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "Something went wrong."

    def __init__(self, message: str | None = None, *, field: str | None = None) -> None:
        self.message = message or self.default_message
        self.field = field
        super().__init__(self.message)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    field: str | None = None,
    details: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a JSON response in the API's single error shape."""
    error: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status_code, headers=headers)


def _field_name(error: Mapping[str, Any]) -> str:
    """Turn a validation error's location, e.g. ("body", "url"), into "url"."""
    if error["type"] == "json_invalid":
        return "body"
    loc = tuple(error["loc"])
    parts = loc[1:] if loc and loc[0] in _LOCATION_SOURCES else loc
    return ".".join(str(part) for part in parts) or "body"


def register_error_handlers(app: FastAPI) -> None:
    """Make every error the app returns use the error envelope."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, field=exc.field)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [{"field": _field_name(err), "message": err["msg"]} for err in exc.errors()]
        return error_response(422, "validation_error", "The request is invalid.", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_")
        return error_response(exc.status_code, code, exc.detail, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(500, AppError.code, AppError.default_message)
