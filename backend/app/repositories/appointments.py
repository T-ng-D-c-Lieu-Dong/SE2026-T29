from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import SlotAlreadyBooked
from app.models import Appointment, AppointmentStatus

ACTIVE_SLOT_CONSTRAINT = "uq_appointments_active_starts_at"


class AppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, customer_name: str, starts_at: datetime) -> Appointment:
        appointment = Appointment(customer_name=customer_name, starts_at=starts_at)
        self.session.add(appointment)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            if ACTIVE_SLOT_CONSTRAINT in str(exc.orig):
                raise SlotAlreadyBooked("This slot already has an active booking") from exc
            raise
        return appointment

    async def get(self, appointment_id: UUID) -> Appointment | None:
        return await self.session.get(Appointment, appointment_id)

    async def list(self, limit: int, offset: int) -> tuple[list[Appointment], int]:
        rows = await self.session.scalars(
            select(Appointment)
            .order_by(Appointment.starts_at, Appointment.created_at)
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(select(func.count()).select_from(Appointment))
        return list(rows), int(total or 0)

    async def booked_starts_between(
        self,
        start: datetime,
        end: datetime,
    ) -> set[datetime]:
        rows = await self.session.scalars(
            select(Appointment.starts_at).where(
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.starts_at >= start,
                Appointment.starts_at < end,
            )
        )
        return set(rows)

    async def export_between(
        self,
        start: datetime,
        end: datetime,
        include_cancelled: bool,
    ) -> list[Appointment]:
        statement = select(Appointment).where(
            Appointment.starts_at >= start,
            Appointment.starts_at < end,
        )
        if not include_cancelled:
            statement = statement.where(Appointment.status == AppointmentStatus.BOOKED.value)
        rows = await self.session.scalars(
            statement.order_by(Appointment.starts_at, Appointment.created_at, Appointment.id)
        )
        return list(rows)

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, appointment: Appointment) -> None:
        await self.session.refresh(appointment)
