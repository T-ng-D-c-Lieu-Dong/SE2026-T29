from __future__ import annotations

import builtins
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain import AppointmentNotFound, InvalidSlot
from app.models import Appointment, AppointmentStatus
from app.repositories import AppointmentRepository
from app.services.fault_injection import BookingFaultInjector
from app.services.notifications import (
    DEFAULT_NOTIFICATION_TIMEOUT_SECONDS,
    BookingNotifier,
    LoggingBookingNotifier,
    NotificationOutcome,
)
from app.telemetry import TelemetryRuntime

BOOKING_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SLOT_MINUTES = 30


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_start_time(starts_at: datetime, now: datetime) -> datetime:
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise InvalidSlot("starts_at must include a UTC offset")

    local_start = starts_at.astimezone(BOOKING_TIMEZONE)
    if local_start.minute not in (0, 30) or local_start.second != 0 or local_start.microsecond != 0:
        raise InvalidSlot("starts_at must be on a 30-minute boundary")

    normalized = local_start.astimezone(UTC)
    if normalized <= now.astimezone(UTC):
        raise InvalidSlot("starts_at must be in the future")
    return normalized


@dataclass(frozen=True, slots=True)
class CreatedBooking:
    appointment: Appointment
    notification: NotificationOutcome


class BookingService:
    def __init__(
        self,
        repository: AppointmentRepository,
        now_provider: Callable[[], datetime] = utc_now,
        fault_injector: BookingFaultInjector | None = None,
        telemetry: TelemetryRuntime | None = None,
        notifier: BookingNotifier | None = None,
        notification_timeout_seconds: float = DEFAULT_NOTIFICATION_TIMEOUT_SECONDS,
    ) -> None:
        self.repository = repository
        self.now_provider = now_provider
        self.fault_injector = fault_injector or BookingFaultInjector()
        self.telemetry = telemetry
        self.notifier = notifier or LoggingBookingNotifier()
        self.notification_timeout_seconds = notification_timeout_seconds

    def _booking_span(self, operation: str) -> Any:
        if self.telemetry is None:
            return nullcontext()
        return self.telemetry.booking_span(operation)

    async def create(self, customer_name: str, starts_at: datetime) -> Appointment:
        with self._booking_span("create"):
            normalized_start = normalize_start_time(starts_at, self.now_provider())
            await self.fault_injector.before_create()
            appointment = await self.repository.create(customer_name, normalized_start)
            await self.repository.commit()
            await self.repository.refresh(appointment)
            return appointment

    async def create_and_notify(self, customer_name: str, starts_at: datetime) -> CreatedBooking:
        # STUB (VT-118): books exactly like create() and sends nothing yet.
        appointment = await self.create(customer_name, starts_at)
        return CreatedBooking(appointment=appointment, notification=NotificationOutcome.DELIVERED)

    async def list(self, limit: int, offset: int) -> tuple[list[Appointment], int]:
        return await self.repository.list(limit, offset)

    async def cancel(self, appointment_id: UUID) -> None:
        with self._booking_span("cancel"):
            appointment = await self.repository.get(appointment_id)
            if appointment is None:
                raise AppointmentNotFound("Appointment was not found")

            if appointment.status == AppointmentStatus.CANCELLED.value:
                return

            appointment.status = AppointmentStatus.CANCELLED.value
            appointment.cancelled_at = self.now_provider().astimezone(UTC)
            await self.repository.commit()

    async def available_slots(self, day: date) -> builtins.list[datetime]:
        local_start = datetime.combine(day, time(0, 0), tzinfo=BOOKING_TIMEZONE)
        local_end = local_start + timedelta(days=1)
        utc_start = local_start.astimezone(UTC)
        utc_end = local_end.astimezone(UTC)
        booked_starts = await self.repository.booked_starts_between(utc_start, utc_end)
        now = self.now_provider().astimezone(UTC)

        slots: list[datetime] = []
        cursor = local_start
        while cursor < local_end:
            cursor_utc = cursor.astimezone(UTC)
            if cursor_utc > now and cursor_utc not in booked_starts:
                slots.append(cursor)
            cursor += timedelta(minutes=SLOT_MINUTES)
        return slots
