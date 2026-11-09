import asyncio
from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.db import get_session
from app.main import create_app


async def test_liveness_does_not_resolve_database_dependency() -> None:
    app = create_app()

    async def unavailable_session() -> AsyncIterator[None]:
        raise AssertionError("liveness must not resolve the database dependency")
        yield

    app.dependency_overrides[get_session] = unavailable_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_returns_503_when_database_is_unavailable() -> None:
    app = create_app()

    class UnavailableSession:
        async def execute(self, statement) -> None:
            raise OSError("database unavailable")

    async def unavailable_session() -> AsyncIterator[UnavailableSession]:
        yield UnavailableSession()

    app.dependency_overrides[get_session] = unavailable_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["database_check_ms"] >= 0


async def test_readiness_times_out_slow_database(monkeypatch) -> None:
    monkeypatch.setenv("BOOKING_DB_TIMEOUT_SECONDS", "0.01")
    get_settings.cache_clear()
    app = create_app()

    class SlowSession:
        async def execute(self, statement) -> None:
            await asyncio.sleep(1)

    async def slow_session() -> AsyncIterator[SlowSession]:
        yield SlowSession()

    app.dependency_overrides[get_session] = slow_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["database_check_ms"] < 500
