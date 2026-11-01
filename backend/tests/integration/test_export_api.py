"""VT-119 API/integration tests for GET /api/exports/appointments (real PostgreSQL)."""

import asyncio
import csv
import io
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import get_session
from app.main import create_app
from app.models import Appointment, AppointmentStatus
from app.services.booking import BOOKING_TIMEZONE

pytestmark = pytest.mark.integration
URL = "/api/exports/appointments"
STAFF = {"X-API-Key": "k-staff"}
ADMIN = {"X-API-Key": "k-admin"}
VIEWER = {"X-API-Key": "k-viewer"}
DAY = date(2026, 11, 20)


@pytest.fixture(autouse=True)
def export_keys(monkeypatch):
    monkeypatch.setenv(
        "BOOKING_EXPORT_API_KEYS", "k-admin:export_admin,k-staff:export_staff,k-viewer:viewer"
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BOOKING_TIMEZONE)


async def seed(factory, name: str, starts_at: datetime, status: str = "booked") -> Appointment:
    async with factory() as session:
        row = Appointment(
            customer_name=name,
            starts_at=starts_at,
            status=status,
            cancelled_at=datetime.now(UTC) if status == "cancelled" else None,
        )
        session.add(row)
        await session.commit()
        return row


def rows(response) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.text)))


def params(date_from: date = DAY, date_to: date = DAY, **extra) -> dict[str, str]:
    return {"from": date_from.isoformat(), "to": date_to.isoformat(), **extra}


async def test_missing_or_wrong_key_is_401_and_leaks_no_data(client, test_session_factory) -> None:
    await seed(test_session_factory, "SecretCustomer", local(DAY, 10))

    for headers in ({}, {"X-API-Key": "wrong"}):
        response = await client.get(URL, params=params(), headers=headers)
        assert response.status_code == 401
        assert "SecretCustomer" not in response.text
        assert not response.headers["content-type"].startswith("text/csv")


async def test_role_without_export_permission_is_403(client, test_session_factory) -> None:
    await seed(test_session_factory, "SecretCustomer", local(DAY, 10))

    response = await client.get(URL, params=params(), headers=VIEWER)

    assert response.status_code == 403
    assert "SecretCustomer" not in response.text


async def test_staff_exports_only_booked_rows_in_requested_days(
    client, test_session_factory
) -> None:
    await seed(test_session_factory, "InScope", local(DAY, 10))
    await seed(test_session_factory, "Cancelled", local(DAY, 11), status="cancelled")
    await seed(test_session_factory, "OtherDay", local(DAY + timedelta(days=3), 10))

    response = await client.get(URL, params=params(), headers=STAFF)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert [r["customer_name"] for r in rows(response)] == ["InScope"]


async def test_scope_boundaries_use_local_day_not_utc_day(client, test_session_factory) -> None:
    await seed(test_session_factory, "prev-day-23:30", local(DAY - timedelta(days=1), 23, 30))
    await seed(test_session_factory, "from-00:00", local(DAY, 0, 0))
    await seed(test_session_factory, "to-23:30", local(DAY, 23, 30))
    await seed(test_session_factory, "next-day-00:00", local(DAY + timedelta(days=1), 0, 0))

    response = await client.get(URL, params=params(), headers=STAFF)

    assert [r["customer_name"] for r in rows(response)] == ["from-00:00", "to-23:30"]


async def test_admin_can_include_cancelled_with_cancelled_at(client, test_session_factory) -> None:
    await seed(test_session_factory, "Booked", local(DAY, 10))
    await seed(test_session_factory, "Cancelled", local(DAY, 11), status="cancelled")

    response = await client.get(URL, params=params(include_cancelled="true"), headers=ADMIN)

    assert response.status_code == 200
    by_name = {r["customer_name"]: r for r in rows(response)}
    assert set(by_name) == {"Booked", "Cancelled"}
    assert by_name["Cancelled"]["status"] == "cancelled"
    assert by_name["Cancelled"]["cancelled_at"] != ""


async def test_staff_cannot_widen_scope_to_cancelled(client, test_session_factory) -> None:
    await seed(test_session_factory, "Cancelled", local(DAY, 11), status="cancelled")

    response = await client.get(URL, params=params(include_cancelled="true"), headers=STAFF)

    assert response.status_code == 403
    assert "Cancelled" not in response.text


@pytest.mark.parametrize(
    "query",
    [
        {"from": "2026-11-21", "to": "2026-11-20"},
        {"from": "2026-11-01", "to": "2026-12-02"},
        {"from": "not-a-date", "to": "2026-11-20"},
        {"to": "2026-11-20"},
        {},
    ],
)
async def test_invalid_scope_is_422_for_authorised_caller(client, query) -> None:
    response = await client.get(URL, params=query, headers=STAFF)

    assert response.status_code == 422


async def test_authentication_precedes_validation(client) -> None:
    bad = {"from": "2026-11-21", "to": "2026-11-20"}

    assert (await client.get(URL, params=bad)).status_code == 401
    assert (await client.get(URL, params=bad, headers=VIEWER)).status_code == 403


async def test_failure_path_database_down_is_503_not_empty_csv(test_session_factory) -> None:
    dead_engine = create_async_engine(
        "postgresql+asyncpg://booking:booking@127.0.0.1:1/booking_test",
        connect_args={"timeout": 1},
    )
    dead_factory = async_sessionmaker(dead_engine, expire_on_commit=False)
    app = create_app()

    async def dead_session():
        async with dead_factory() as session:
            yield session

    app.dependency_overrides[get_session] = dead_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.get(URL, params=params(), headers=STAFF)
    finally:
        await dead_engine.dispose()

    assert response.status_code == 503
    assert not response.headers["content-type"].startswith("text/csv")
    assert "customer_name" not in response.text


async def test_export_is_deterministic_and_has_no_side_effects(
    client, test_session_factory
) -> None:
    for hour in (9, 10, 11):
        await seed(test_session_factory, f"C{hour}", local(DAY, hour))

    first = await client.get(URL, params=params(), headers=STAFF)
    second = await client.get(URL, params=params(), headers=STAFF)

    assert first.status_code == second.status_code == 200
    assert first.content == second.content


async def test_export_neutralises_formula_injection_end_to_end(
    client, test_session_factory
) -> None:
    await seed(test_session_factory, '=HYPERLINK("http://evil")', local(DAY, 10))

    response = await client.get(URL, params=params(), headers=STAFF)

    assert rows(response)[0]["customer_name"].startswith("'=")


async def test_repeated_cancel_does_not_rewrite_cancelled_at_seen_by_export(client) -> None:
    starts_at = datetime.now(BOOKING_TIMEZONE).replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(days=2)
    created = await client.post(
        "/api/appointments",
        json={"customer_name": "Cuong", "starts_at": starts_at.isoformat()},
    )
    appointment_id = created.json()["id"]
    day = starts_at.date()

    await client.delete(f"/api/appointments/{appointment_id}")
    first = await client.get(URL, params=params(day, day, include_cancelled="true"), headers=ADMIN)
    await asyncio.sleep(0.01)
    await client.delete(f"/api/appointments/{appointment_id}")
    second = await client.get(URL, params=params(day, day, include_cancelled="true"), headers=ADMIN)

    assert rows(first)[0]["cancelled_at"] != ""
    assert rows(first) == rows(second)


async def test_concurrent_bookings_never_export_duplicate_active_slot(
    client, test_session_factory
) -> None:
    starts_at = datetime.now(BOOKING_TIMEZONE).replace(
        hour=14, minute=0, second=0, microsecond=0
    ) + timedelta(days=3)
    day = starts_at.date()

    results = await asyncio.gather(
        *[
            client.post(
                "/api/appointments",
                json={"customer_name": f"C{i}", "starts_at": starts_at.isoformat()},
            )
            for i in range(10)
        ]
    )

    assert sorted(r.status_code for r in results).count(201) == 1
    assert sorted(r.status_code for r in results).count(409) == 9
    exported = await client.get(URL, params=params(day, day), headers=STAFF)
    assert len(rows(exported)) == 1
    async with test_session_factory() as session:
        booked = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.status == AppointmentStatus.BOOKED.value)
        )
        assert booked == 1


async def test_export_during_concurrent_writes_stays_consistent(
    client, test_session_factory
) -> None:
    base = datetime.now(BOOKING_TIMEZONE).replace(minute=0, second=0, microsecond=0) + timedelta(
        days=4
    )
    day = base.date()

    async def book(hour: int):
        return await client.post(
            "/api/appointments",
            json={"customer_name": f"W{hour}", "starts_at": base.replace(hour=hour).isoformat()},
        )

    exports = [client.get(URL, params=params(day, day), headers=STAFF) for _ in range(15)]
    writes = [book(h) for h in range(8, 16)]
    results = await asyncio.gather(*exports, *writes)

    for response in results[:15]:
        assert response.status_code == 200
        starts = [r["starts_at"] for r in rows(response)]
        assert len(starts) == len(set(starts))
