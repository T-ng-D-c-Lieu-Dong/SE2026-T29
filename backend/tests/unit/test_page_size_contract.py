import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_page_size_from_environment(monkeypatch):
    monkeypatch.setenv("BOOKING_DEFAULT_PAGE_SIZE", "7")
    assert Settings(_env_file=None).default_page_size == 7


@pytest.mark.parametrize("value", ["0", "101", "invalid"])
def test_invalid_page_size_fails(value, monkeypatch):
    monkeypatch.setenv("BOOKING_DEFAULT_PAGE_SIZE", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.asyncio
async def test_repository_failure_is_not_empty_success(monkeypatch):
    from app.services.booking import BookingService

    class BrokenRepository:
        async def list(self, limit, offset):
            raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await BookingService(BrokenRepository()).list(7, 0)


@pytest.mark.asyncio
async def test_api_uses_configured_limit_and_returns_business_data(monkeypatch):
    from datetime import UTC, datetime
    from uuid import uuid4

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api import appointments
    from app.config import get_settings
    from app.db import get_session

    class FakeService:
        def __init__(self, repository):
            pass

        async def list(self, limit, offset):
            assert (limit, offset) == (7, 1)
            from types import SimpleNamespace

            item = SimpleNamespace(
                id=uuid4(),
                customer_name="Lan",
                starts_at=datetime(2030, 1, 1, tzinfo=UTC),
                status="booked",
                created_at=datetime(2029, 1, 1, tzinfo=UTC),
                cancelled_at=None,
            )
            return [item], 12

    monkeypatch.setenv("BOOKING_DEFAULT_PAGE_SIZE", "7")
    get_settings.cache_clear()
    monkeypatch.setattr(appointments, "BookingService", FakeService)
    app = FastAPI()
    app.include_router(appointments.router)
    app.dependency_overrides[get_session] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/appointments?offset=1")
        assert response.status_code == 200
        body = response.json()
        assert (body["limit"], body["offset"], body["total"]) == (7, 1, 12)
        assert body["items"][0]["customer_name"] == "Lan"
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("value", [1, 100])
def test_boundary_config(value, monkeypatch):
    monkeypatch.setenv("BOOKING_DEFAULT_PAGE_SIZE", str(value))
    assert Settings(_env_file=None).default_page_size == value


def test_default_is_20(monkeypatch):
    monkeypatch.delenv("BOOKING_DEFAULT_PAGE_SIZE", raising=False)
    assert Settings(_env_file=None).default_page_size == 20


@pytest.mark.asyncio
async def test_explicit_limit_and_invalid_query(monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api import appointments
    from app.config import get_settings
    from app.db import get_session

    class FakeService:
        def __init__(self, repository):
            pass

        async def list(self, limit, offset):
            assert (limit, offset) == (3, 0)
            return [], 0

    monkeypatch.setenv("BOOKING_DEFAULT_PAGE_SIZE", "7")
    get_settings.cache_clear()
    monkeypatch.setattr(appointments, "BookingService", FakeService)
    app = FastAPI()
    app.include_router(appointments.router)
    app.dependency_overrides[get_session] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/appointments?limit=3")
            assert response.status_code == 200
            assert response.json() == {"items": [], "total": 0, "limit": 3, "offset": 0}
            assert (await client.get("/api/appointments?limit=101")).status_code == 422
            assert (await client.get("/api/appointments?limit=0")).status_code == 422
    finally:
        get_settings.cache_clear()
