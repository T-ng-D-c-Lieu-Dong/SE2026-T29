from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from app.domain import AppointmentNotFound, InvalidSlot
from app.models import AppointmentStatus
from app.repositories import AppointmentRepository
from app.services.booking import BOOKING_TIMEZONE, BookingService, normalize_start_time
from app.services.fault_injection import BookingFaultInjector, InjectedBookingFault
from app.telemetry import TelemetryRuntime

NOW = datetime(2026, 10, 7, 3, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.created: tuple[str, datetime] | None = None
        self.appointment = None
        self.commits = 0

    async def create(self, customer_name: str, starts_at: datetime):
        self.created = (customer_name, starts_at)
        self.appointment = SimpleNamespace(
            id=uuid4(),
            customer_name=customer_name,
            starts_at=starts_at,
            status=AppointmentStatus.BOOKED.value,
            created_at=NOW,
            cancelled_at=None,
        )
        return self.appointment

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, appointment) -> None:
        return None

    async def get(self, appointment_id):
        return self.appointment

    async def list(self, limit: int, offset: int):
        items = [] if self.appointment is None else [self.appointment]
        return items[offset : offset + limit], len(items)

    async def booked_starts_between(self, start: datetime, end: datetime):
        if self.appointment is None or self.appointment.status != AppointmentStatus.BOOKED.value:
            return set()
        return {self.appointment.starts_at}


class FakeTelemetry:
    def __init__(self) -> None:
        self.operations: list[str] = []

    @contextmanager
    def booking_span(self, operation: str):
        self.operations.append(operation)
        yield


def test_normalize_start_time_converts_to_utc() -> None:
    starts_at = datetime(2026, 10, 10, 10, 0, tzinfo=BOOKING_TIMEZONE)

    normalized = normalize_start_time(starts_at, NOW)

    assert normalized == datetime(2026, 10, 10, 3, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "starts_at",
    [
        datetime(2026, 10, 10, 10, 15, tzinfo=BOOKING_TIMEZONE),
        datetime(2026, 10, 10, 10, 30, 1, tzinfo=BOOKING_TIMEZONE),
        datetime(2026, 10, 7, 10, 0, tzinfo=BOOKING_TIMEZONE),
        datetime(2026, 10, 10, 10, 0),
    ],
)
def test_normalize_start_time_rejects_invalid_slots(starts_at: datetime) -> None:
    with pytest.raises(InvalidSlot):
        normalize_start_time(starts_at, NOW)


async def test_create_uses_normalized_time_and_commits() -> None:
    repository = FakeRepository()
    telemetry = FakeTelemetry()
    service = BookingService(
        cast(AppointmentRepository, repository),
        now_provider=lambda: NOW,
        telemetry=cast(TelemetryRuntime, telemetry),
    )

    appointment = await service.create(
        "Cuong",
        datetime(2026, 10, 10, 10, 0, tzinfo=BOOKING_TIMEZONE),
    )

    assert repository.created == ("Cuong", datetime(2026, 10, 10, 3, 0, tzinfo=UTC))
    assert repository.commits == 1
    assert appointment.status == AppointmentStatus.BOOKED.value
    assert telemetry.operations == ["create"]


async def test_create_injects_error_before_repository_write() -> None:
    repository = FakeRepository()
    injector = BookingFaultInjector(
        mode="error",
        until=NOW + timedelta(hours=1),
        now_provider=lambda: NOW,
        random_provider=lambda: 0.0,
    )
    service = BookingService(
        cast(AppointmentRepository, repository),
        now_provider=lambda: NOW,
        fault_injector=injector,
    )

    with pytest.raises(InjectedBookingFault):
        await service.create(
            "Cuong",
            datetime(2026, 10, 10, 10, 0, tzinfo=BOOKING_TIMEZONE),
        )

    assert repository.created is None
    assert repository.commits == 0


async def test_cancel_is_idempotent() -> None:
    repository = FakeRepository()
    telemetry = FakeTelemetry()
    service = BookingService(
        cast(AppointmentRepository, repository),
        now_provider=lambda: NOW,
        telemetry=cast(TelemetryRuntime, telemetry),
    )
    appointment = await service.create(
        "Cuong",
        datetime(2026, 10, 10, 10, 0, tzinfo=BOOKING_TIMEZONE),
    )

    await service.cancel(appointment.id)
    await service.cancel(appointment.id)

    assert appointment.status == AppointmentStatus.CANCELLED.value
    assert appointment.cancelled_at == NOW
    assert repository.commits == 2
    assert telemetry.operations == ["create", "cancel", "cancel"]


async def test_cancel_unknown_appointment() -> None:
    repository = FakeRepository()
    service = BookingService(cast(AppointmentRepository, repository), now_provider=lambda: NOW)

    with pytest.raises(AppointmentNotFound):
        await service.cancel(uuid4())


async def test_available_slots_excludes_booked_slot() -> None:
    repository = FakeRepository()
    service = BookingService(cast(AppointmentRepository, repository), now_provider=lambda: NOW)
    booked = await service.create(
        "Cuong",
        datetime(2026, 10, 10, 10, 0, tzinfo=BOOKING_TIMEZONE),
    )

    slots = await service.available_slots(date(2026, 10, 10))

    assert booked.starts_at.astimezone(BOOKING_TIMEZONE) not in slots
    assert len(slots) == 47
