"""Request validation must not echo customer input or need a live database."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import appointments
from app.db import get_session
from app.main import create_app

SECRET = "private-customer-data"
VALID_PAYLOAD = {"customer_name": "Cuong", "starts_at": "2099-11-25T09:30:00+07:00"}


@pytest_asyncio.fixture
async def validation_client(monkeypatch) -> AsyncIterator[AsyncClient]:
    application = create_app()

    async def no_database() -> AsyncIterator[None]:
        yield None

    def unexpected_booking_service(*args, **kwargs):
        raise AssertionError("invalid requests must not reach the booking service")

    application.dependency_overrides[get_session] = no_database
    monkeypatch.setattr(appointments, "booking_service", unexpected_booking_service)
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
        headers={"X-User-Id": "validation-test"},
    ) as client:
        yield client


def assert_safe_validation(response, location: list[str], error_type: str) -> None:
    assert response.status_code == 422
    assert len(response.content) < 4096
    assert SECRET not in response.text
    errors = response.json()["detail"]
    assert any(error["loc"] == location and error["type"] == error_type for error in errors)
    assert all(set(error) == {"type", "loc", "msg"} for error in errors)
    assert all(isinstance(error["msg"], str) and error["msg"] for error in errors)


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("customer_name", SECRET * 50_000, "string_too_long"),
        ("customer_name", {"private": SECRET}, "string_type"),
        ("customer_name", "   ", "value_error"),
        ("starts_at", SECRET * 50_000, "datetime_from_date_parsing"),
        ("starts_at", "2099-11-25T09:30:00", "value_error"),
        ("owner_id", SECRET * 50_000, "string_too_long"),
    ],
    ids=["large-name", "object-name", "blank-name", "large-date", "naive-date", "large-owner"],
)
async def test_invalid_body_has_small_errors_without_input_or_context(
    validation_client, field, value, error_type
) -> None:
    response = await validation_client.post(
        "/api/appointments", json={**VALID_PAYLOAD, field: value}
    )

    assert_safe_validation(response, ["body", field], error_type)


async def test_missing_fields_keep_both_error_locations(validation_client) -> None:
    response = await validation_client.post("/api/appointments", json={"private": SECRET})

    assert_safe_validation(response, ["body", "customer_name"], "missing")
    assert_safe_validation(response, ["body", "starts_at"], "missing")


async def test_invalid_json_keeps_decode_error_without_echoing_body(validation_client) -> None:
    response = await validation_client.post(
        "/api/appointments",
        content='{"customer_name":"' + SECRET + '","starts_at":}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors[0]["type"] == "json_invalid"
    assert errors[0]["loc"][0] == "body"
    assert set(errors[0]) == {"type", "loc", "msg"}
    assert SECRET not in response.text


async def test_invalid_query_does_not_echo_large_date(validation_client) -> None:
    response = await validation_client.get("/api/slots", params={"date": SECRET * 500})

    assert_safe_validation(response, ["query", "date"], "date_from_datetime_parsing")


async def test_invalid_path_keeps_uuid_error_without_echoing_identifier(validation_client) -> None:
    response = await validation_client.get(f"/api/appointments/{SECRET}")

    assert_safe_validation(response, ["path", "appointment_id"], "uuid_parsing")
