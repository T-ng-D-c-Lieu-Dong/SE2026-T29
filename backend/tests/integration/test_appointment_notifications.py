"""VT-118 API tests on PostgreSQL: notifying ``appointment.created`` never breaks the booking.

Written before the implementation (test-first). Partitions used (docs/vt118/02-test-strategy.md):

* notifier behaviour N1 ok / N2 raise / N3 hang -> response ``notification_status``
  ``sent`` / ``failed`` / ``timeout`` (every output class is produced at least once);
* ``customer_name`` length after strip: L1 1..100 valid, L2 blank, L3 > 100 (incl. 1 MB);
* request outcome: 201 created, 409 conflict, 422 invalid, 500 injected fault.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.appointments import get_booking_notifier
from app.config import get_settings
from app.db import get_session
from app.main import create_app
from app.models import Appointment, AppointmentStatus
from app.services.booking import BOOKING_TIMEZONE
from app.services.notifications import APPOINTMENT_CREATED, AppointmentCreatedEvent

pytestmark = pytest.mark.integration

URL = "/api/appointments"


class ProgrammableNotifier:
    def __init__(self) -> None:
        self.behaviour = "ok"
        self.events: list[AppointmentCreatedEvent] = []
        self.probe: Callable[[AppointmentCreatedEvent], Awaitable[object]] | None = None
        self.probes: list[object] = []

    async def send(self, event: AppointmentCreatedEvent) -> None:
        self.events.append(event)
        if self.probe is not None:
            self.probes.append(await self.probe(event))
        if self.behaviour == "raise":
            raise ConnectionError("notification channel is down")
        if self.behaviour == "hang":
            await asyncio.Event().wait()


@pytest.fixture
def notifier() -> ProgrammableNotifier:
    return ProgrammableNotifier()


@pytest_asyncio.fixture
async def api(test_session_factory, notifier) -> AsyncIterator[AsyncClient]:
    application = create_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[get_booking_notifier] = lambda: notifier
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    application.dependency_overrides.clear()


@pytest.fixture
def notification_timeout(monkeypatch) -> Iterator[Callable[[float], None]]:
    def apply(seconds: float) -> None:
        monkeypatch.setenv("BOOKING_NOTIFICATION_TIMEOUT_SECONDS", str(seconds))
        get_settings.cache_clear()

    yield apply
    get_settings.cache_clear()


def slot(index: int = 0, days: int = 2) -> datetime:
    day = datetime.now(BOOKING_TIMEZONE).date() + timedelta(days=days)
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=BOOKING_TIMEZONE)
    return midnight + timedelta(minutes=30 * index)


async def booked_rows(test_session_factory) -> int:
    async with test_session_factory() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.status == AppointmentStatus.BOOKED.value)
        )
    return int(total or 0)


@pytest.mark.parametrize(
    ("behaviour", "expected_status"),
    [
        pytest.param("ok", "sent", id="TC08-N1-sent"),
        pytest.param("raise", "failed", id="TC09-N2-failed"),
        pytest.param("hang", "timeout", id="TC10-N3-timeout"),
    ],
)
async def test_tc08_tc10_booking_is_kept_and_notification_status_reported(
    api,
    notifier,
    notification_timeout,
    test_session_factory,
    behaviour: str,
    expected_status: str,
) -> None:
    notification_timeout(0.2)
    notifier.behaviour = behaviour
    starts_at = slot(20)

    started = time.perf_counter()
    response = await api.post(
        URL, json={"customer_name": " Cuong ", "starts_at": starts_at.isoformat()}
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 201
    body = response.json()
    assert body["notification_status"] == expected_status
    assert elapsed < 0.2 + 1.5

    assert len(notifier.events) == 1
    event = notifier.events[0]
    assert event.event_type == APPOINTMENT_CREATED
    assert str(event.appointment_id) == body["id"]
    assert event.customer_name == "Cuong"
    assert event.starts_at == starts_at

    async with test_session_factory() as session:
        saved = await session.get(Appointment, UUID(body["id"]))
    assert saved is not None
    assert saved.status == AppointmentStatus.BOOKED.value


async def test_tc11_channel_runs_after_commit_without_holding_a_db_connection(
    api,
    notifier,
    test_session_factory,
) -> None:
    engine = test_session_factory.kw["bind"]

    async def probe(event: AppointmentCreatedEvent) -> tuple[int, bool]:
        checked_out = engine.pool.checkedout()
        async with test_session_factory() as session:
            visible = await session.get(Appointment, event.appointment_id)
        return checked_out, visible is not None

    notifier.probe = probe

    response = await api.post(
        URL, json={"customer_name": "Cuong", "starts_at": slot(21).isoformat()}
    )

    assert response.status_code == 201
    # (connections checked out while the channel runs, booking visible to another session)
    assert notifier.probes == [(0, True)]


async def test_tc12_conflicting_booking_is_not_notified(api, notifier) -> None:
    payload = {"customer_name": "Cuong", "starts_at": slot(22).isoformat()}

    first = await api.post(URL, json=payload)
    second = await api.post(URL, json={**payload, "customer_name": "Lan"})

    assert (first.status_code, second.status_code) == (201, 409)
    assert [str(event.appointment_id) for event in notifier.events] == [first.json()["id"]]


@pytest.mark.parametrize(
    ("customer_name", "expected_status"),
    [
        pytest.param("C", 201, id="TC14a-L1-1-char"),
        pytest.param("N" * 100, 201, id="TC14b-L1-100-chars"),
        pytest.param("   ", 422, id="TC14c-L2-blank"),
        pytest.param("N" * 101, 422, id="TC14d-L3-101-chars"),
        pytest.param("X" * 1_000_000, 422, id="TC13-L3-large-1MB"),
    ],
)
async def test_tc13_tc14_customer_name_partitions(
    api,
    notifier,
    test_session_factory,
    customer_name: str,
    expected_status: int,
) -> None:
    started = time.perf_counter()
    response = await api.post(
        URL, json={"customer_name": customer_name, "starts_at": slot(23).isoformat()}
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == expected_status
    if expected_status == 201:
        assert response.json()["notification_status"] == "sent"
        assert [event.customer_name for event in notifier.events] == [customer_name]
        assert await booked_rows(test_session_factory) == 1
    else:
        assert notifier.events == []
        assert await booked_rows(test_session_factory) == 0
        assert elapsed < 1.0


async def test_tc15_injected_fault_returns_500_and_is_not_notified(
    api,
    notifier,
    monkeypatch,
    test_session_factory,
) -> None:
    monkeypatch.setenv("BOOKING_FAULT_MODE", "error")
    monkeypatch.setenv("BOOKING_FAULT_RATE", "1")
    monkeypatch.setenv(
        "BOOKING_FAULT_UNTIL", (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    )
    get_settings.cache_clear()
    try:
        response = await api.post(
            URL, json={"customer_name": "Cuong", "starts_at": slot(24).isoformat()}
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 500
    assert notifier.events == []
    assert await booked_rows(test_session_factory) == 0


async def test_tc16_sixty_concurrent_bookings_survive_a_failing_channel(
    api,
    notifier,
    test_session_factory,
) -> None:
    notifier.behaviour = "raise"

    responses = await asyncio.gather(
        *(
            api.post(
                URL,
                json={"customer_name": f"Khach {index}", "starts_at": slot(index, 3).isoformat()},
            )
            for index in range(60)
        )
    )

    assert [response.status_code for response in responses] == [201] * 60
    assert {response.json()["notification_status"] for response in responses} == {"failed"}
    assert len(notifier.events) == 60
    assert await booked_rows(test_session_factory) == 60


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Residual risk (evidence/02-oversized-422-echo.log): FastAPI's default 422 handler echoes "
        "the rejected input, so a 1 MB customer_name produces a ~1 MB error response."
    ),
)
async def test_tc19_rejection_of_large_input_has_a_bounded_response(api) -> None:
    response = await api.post(
        URL, json={"customer_name": "X" * 1_000_000, "starts_at": slot(25).isoformat()}
    )

    assert response.status_code == 422
    assert len(response.content) < 4_096
