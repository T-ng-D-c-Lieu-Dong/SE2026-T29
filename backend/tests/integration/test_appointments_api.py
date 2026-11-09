import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import Appointment, AppointmentStatus
from app.services.booking import BOOKING_TIMEZONE

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def explicit_regression_identity(client):
    """Existing business tests now use the required private API identity contract."""
    client.headers["X-User-Id"] = "regression-user"


def future_slot(days: int = 2, hour: int = 10) -> datetime:
    day = datetime.now(BOOKING_TIMEZONE).date() + timedelta(days=days)
    return datetime.combine(day, datetime.min.time(), tzinfo=BOOKING_TIMEZONE).replace(hour=hour)


async def test_create_booking_persists(client, test_session_factory) -> None:
    starts_at = future_slot()

    response = await client.post(
        "/api/appointments",
        json={"customer_name": " Cuong ", "starts_at": starts_at.isoformat()},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["customer_name"] == "Cuong"
    assert datetime.fromisoformat(payload["starts_at"]).astimezone(UTC) == starts_at.astimezone(UTC)

    async with test_session_factory() as session:
        saved = await session.get(Appointment, UUID(payload["id"]))
        assert saved is not None
        assert saved.status == AppointmentStatus.BOOKED.value


async def test_error_fault_returns_500_before_database_write(
    client,
    test_session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setenv("BOOKING_FAULT_MODE", "error")
    monkeypatch.setenv("BOOKING_FAULT_RATE", "1")
    monkeypatch.setenv(
        "BOOKING_FAULT_UNTIL",
        (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    get_settings.cache_clear()

    try:
        response = await client.post(
            "/api/appointments",
            json={
                "customer_name": "Cuong",
                "starts_at": future_slot().isoformat(),
            },
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Injected booking failure"}
        async with test_session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(Appointment))
            assert count == 0
    finally:
        get_settings.cache_clear()


async def test_concurrent_booking_same_slot(client, test_session_factory) -> None:
    starts_at = future_slot()
    payload = {"customer_name": "Cuong", "starts_at": starts_at.isoformat()}

    first, second = await asyncio.gather(
        client.post("/api/appointments", json=payload),
        client.post("/api/appointments", json={**payload, "customer_name": "Lan"}),
    )

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    async with test_session_factory() as session:
        active_count = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.status == AppointmentStatus.BOOKED.value)
        )
        assert active_count == 1


async def test_invalid_slot_returns_422(client) -> None:
    invalid_start = future_slot().replace(minute=15)

    response = await client.post(
        "/api/appointments",
        json={"customer_name": "Cuong", "starts_at": invalid_start.isoformat()},
    )

    assert response.status_code == 422


async def test_cancel_is_idempotent_and_allows_rebooking(client) -> None:
    starts_at = future_slot()
    create_response = await client.post(
        "/api/appointments",
        json={"customer_name": "Cuong", "starts_at": starts_at.isoformat()},
    )
    appointment_id = create_response.json()["id"]

    first_cancel = await client.delete(f"/api/appointments/{appointment_id}")
    second_cancel = await client.delete(f"/api/appointments/{appointment_id}")
    rebook = await client.post(
        "/api/appointments",
        json={"customer_name": "Lan", "starts_at": starts_at.isoformat()},
    )

    assert first_cancel.status_code == 204
    assert second_cancel.status_code == 204
    assert rebook.status_code == 201


async def test_cancel_unknown_id_returns_404(client) -> None:
    response = await client.delete(f"/api/appointments/{uuid4()}")

    assert response.status_code == 404


async def test_list_appointments_is_paginated(client) -> None:
    for day_offset in (2, 3):
        response = await client.post(
            "/api/appointments",
            json={
                "customer_name": f"Customer {day_offset}",
                "starts_at": future_slot(days=day_offset).isoformat(),
            },
        )
        assert response.status_code == 201

    response = await client.get("/api/appointments", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1


async def test_slots_exclude_active_booking(client) -> None:
    starts_at = future_slot()
    create_response = await client.post(
        "/api/appointments",
        json={"customer_name": "Cuong", "starts_at": starts_at.isoformat()},
    )
    assert create_response.status_code == 201

    response = await client.get(
        "/api/slots",
        params={"date": starts_at.astimezone(BOOKING_TIMEZONE).date().isoformat()},
    )

    assert response.status_code == 200
    returned = {datetime.fromisoformat(item["starts_at"]) for item in response.json()}
    assert starts_at not in returned
