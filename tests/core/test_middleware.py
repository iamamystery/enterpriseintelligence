import logging
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import NotFoundError
from app.core.middleware import (
    REQUEST_ID_HEADER,
    ErrorHandlingMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)


@pytest.fixture(autouse=True)
def _undo_alembic_log_disabling() -> None:
    # tests/conftest.py runs Alembic migrations in-process (session-scoped
    # autouse fixture), and Alembic's env.py calls logging.config.fileConfig()
    # with its default disable_existing_loggers=True, which silently disables
    # any already-imported app logger not named in alembic.ini. Undo that here
    # so caplog can actually observe records from our loggers.
    for name in ("app.request", "app.error"):
        logging.getLogger(name).disabled = False


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    async def boom() -> None:
        raise ValueError("kaboom")

    @app.get("/domain-error")
    async def domain_error() -> None:
        raise NotFoundError("widget not found")

    # Same add-order as app/main.py: ErrorHandling innermost, RequestID outermost.
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)
    return app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_generates_request_id_when_absent(client: AsyncClient):
    response = await client.get("/ok")
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]


async def test_preserves_valid_incoming_request_id(client: AsyncClient):
    response = await client.get("/ok", headers={REQUEST_ID_HEADER: "upstream-abc123"})
    assert response.headers[REQUEST_ID_HEADER] == "upstream-abc123"


async def test_replaces_unsafe_incoming_request_id(client: AsyncClient):
    response = await client.get("/ok", headers={REQUEST_ID_HEADER: "not safe\r\nInjected: true"})
    assert response.headers[REQUEST_ID_HEADER] != "not safe\r\nInjected: true"


async def test_unhandled_exception_returns_generic_500(client: AsyncClient):
    response = await client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


async def test_unhandled_exception_is_logged_with_request_id(client: AsyncClient, caplog):
    with caplog.at_level(logging.ERROR, logger="app.error"):
        response = await client.get("/boom")
    request_id = response.headers[REQUEST_ID_HEADER]
    assert any(request_id in record.getMessage() for record in caplog.records)


async def test_domain_error_is_not_shadowed_by_error_handling_middleware(client: AsyncClient):
    response = await client.get("/domain-error")
    assert response.status_code == 404
    assert response.json() == {"detail": "widget not found"}


async def test_successful_request_is_logged(client: AsyncClient, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = await client.get("/ok")
    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("GET /ok 200" in message for message in messages)


async def test_failed_request_is_logged_with_500_status(client: AsyncClient, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        await client.get("/boom")
    messages = [record.getMessage() for record in caplog.records]
    assert any("GET /boom 500" in message for message in messages)
