from __future__ import annotations

import builtins
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain import AccessDeniedError, AppointmentNotFound, InvalidSlot, SlotAlreadyBooked
from app.models import Appointment, AppointmentStatus
from app.ownership import is_quarantined_owner
from app.repositories import AppointmentRepository
from app.services.fault_injection import BookingFaultInjector
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


class BookingService:
    def __init__(
        self,
        repository: AppointmentRepository,
        now_provider: Callable[[], datetime] = utc_now,
        fault_injector: BookingFaultInjector | None = None,
        telemetry: TelemetryRuntime | None = None,
    ) -> None:
        self.repository = repository
        self.now_provider = now_provider
        self.fault_injector = fault_injector or BookingFaultInjector()
        self.telemetry = telemetry

    def _booking_span(self, operation: str) -> Any:
        if self.telemetry is None:
            return nullcontext()
        return self.telemetry.booking_span(operation)

    async def _get_appointment(
        self,
        appointment_id: UUID,
        include_deleted: bool = False,
    ) -> Appointment | None:
        try:
            return await self.repository.get(appointment_id, include_deleted=include_deleted)
        except TypeError:
            return await self.repository.get(appointment_id)

    async def create(
        self,
        customer_name: str,
        starts_at: datetime,
        owner_id: str = "anonymous",
    ) -> Appointment:
        with self._booking_span("create"):
            normalized_start = normalize_start_time(starts_at, self.now_provider())
            await self.fault_injector.before_create()
            try:
                appointment = await self.repository.create(
                    customer_name=customer_name,
                    starts_at=normalized_start,
                    owner_id=owner_id,
                )
            except TypeError:
                appointment = await self.repository.create(
                    customer_name=customer_name,
                    starts_at=normalized_start,
                )
            await self.repository.commit()
            if hasattr(self.repository, "refresh"):
                await self.repository.refresh(appointment)
            return appointment

    async def get(self, appointment_id: UUID, caller_id: str | None = None) -> Appointment:
        appointment = await self._get_appointment(appointment_id, include_deleted=False)
        if appointment is None or getattr(appointment, "is_deleted", False):
            raise AppointmentNotFound("Appointment was not found")

        owner = getattr(appointment, "owner_id", None)
        if getattr(appointment, "owner_access_enabled", True) is False or (
            owner is not None and is_quarantined_owner(owner)
        ):
            raise AppointmentNotFound("Appointment was not found")
        if caller_id is not None and owner is not None and owner != caller_id:
            raise AppointmentNotFound("Appointment was not found")

        return appointment

    async def list(
        self,
        limit: int,
        offset: int,
        owner_id: str | None = None,
    ) -> tuple[list[Appointment], int]:
        try:
            return await self.repository.list(limit, offset, owner_id=owner_id)
        except TypeError:
            return await self.repository.list(limit, offset)

    async def list_trash(
        self,
        caller_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Appointment], int]:
        return await self.repository.list_trash(owner_id=caller_id, limit=limit, offset=offset)

    async def soft_delete(self, appointment_id: UUID, caller_id: str) -> Appointment:
        with self._booking_span("soft_delete"):
            appointment = await self._get_appointment(appointment_id, include_deleted=True)
            if appointment is None:
                raise AppointmentNotFound("Appointment was not found")

            owner = getattr(appointment, "owner_id", "anonymous")
            if getattr(appointment, "owner_access_enabled", True) is False or is_quarantined_owner(
                owner
            ):
                raise AccessDeniedError("Historical ownership has not been verified")
            if owner != caller_id:
                raise AccessDeniedError("You do not have permission to delete this appointment")

            if getattr(appointment, "is_deleted", False):
                return appointment

            appointment.is_deleted = True
            appointment.deleted_at = self.now_provider().astimezone(UTC)
            await self.repository.commit()
            if hasattr(self.repository, "refresh"):
                await self.repository.refresh(appointment)
            return appointment

    async def restore(self, appointment_id: UUID, caller_id: str) -> Appointment:
        with self._booking_span("restore"):
            appointment = await self._get_appointment(appointment_id, include_deleted=True)
            if appointment is None:
                raise AppointmentNotFound("Appointment was not found")

            owner = getattr(appointment, "owner_id", "anonymous")
            if getattr(appointment, "owner_access_enabled", True) is False or is_quarantined_owner(
                owner
            ):
                raise AccessDeniedError("Historical ownership has not been verified")
            if owner != caller_id:
                raise AccessDeniedError("You do not have permission to restore this appointment")

            if not getattr(appointment, "is_deleted", False):
                return appointment

            now = self.now_provider().astimezone(UTC)
            if appointment.starts_at.astimezone(UTC) <= now:
                raise InvalidSlot("Cannot restore an appointment with a slot in the past")

            if appointment.status == AppointmentStatus.BOOKED.value:
                is_conflict = False
                if hasattr(self.repository, "is_slot_booked"):
                    is_conflict = await self.repository.is_slot_booked(
                        appointment.starts_at,
                        exclude_id=appointment.id,
                    )
                else:
                    booked = await self.repository.booked_starts_between(
                        appointment.starts_at,
                        appointment.starts_at + timedelta(minutes=1),
                    )
                    is_conflict = appointment.starts_at in booked

                if is_conflict:
                    raise SlotAlreadyBooked("This slot already has an active booking")

            appointment.is_deleted = False
            appointment.deleted_at = None
            await self.repository.commit()
            if hasattr(self.repository, "refresh"):
                await self.repository.refresh(appointment)
            return appointment

    async def cancel(self, appointment_id: UUID, caller_id: str | None = None) -> None:
        with self._booking_span("cancel"):
            appointment = await self._get_appointment(appointment_id, include_deleted=True)
            if appointment is None or getattr(appointment, "is_deleted", False):
                raise AppointmentNotFound("Appointment was not found")

            owner = getattr(appointment, "owner_id", None)
            if getattr(appointment, "owner_access_enabled", True) is False or (
                owner is not None and is_quarantined_owner(owner)
            ):
                raise AccessDeniedError("Historical ownership has not been verified")
            if caller_id is not None and owner is not None and owner != caller_id:
                raise AccessDeniedError("You do not have permission to cancel this appointment")

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
