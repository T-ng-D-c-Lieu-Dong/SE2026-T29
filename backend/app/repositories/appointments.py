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

    async def create(
        self,
        customer_name: str,
        starts_at: datetime,
        owner_id: str | None = None,
    ) -> Appointment:
        effective_owner = owner_id or customer_name
        appointment = Appointment(
            customer_name=customer_name,
            starts_at=starts_at,
            owner_id=effective_owner,
        )
        self.session.add(appointment)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            if ACTIVE_SLOT_CONSTRAINT in str(exc.orig):
                raise SlotAlreadyBooked("This slot already has an active booking") from exc
            raise
        return appointment

    async def get(self, appointment_id: UUID, include_deleted: bool = False) -> Appointment | None:
        query = select(Appointment).where(Appointment.id == appointment_id)
        if not include_deleted:
            query = query.where(Appointment.is_deleted.is_(False))
        return await self.session.scalar(query)

    async def list(
        self,
        limit: int,
        offset: int,
        owner_id: str | None = None,
    ) -> tuple[list[Appointment], int]:
        query = select(Appointment).where(Appointment.is_deleted.is_(False))
        count_query = (
            select(func.count()).select_from(Appointment).where(Appointment.is_deleted.is_(False))
        )

        if owner_id is not None:
            query = query.where(Appointment.owner_id == owner_id)
            count_query = count_query.where(Appointment.owner_id == owner_id)

        rows = await self.session.scalars(
            query.order_by(Appointment.starts_at, Appointment.created_at)
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows), int(total or 0)

    async def list_trash(
        self,
        owner_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list[Appointment], int]:
        query = (
            select(Appointment)
            .where(Appointment.is_deleted.is_(True), Appointment.owner_id == owner_id)
            .order_by(Appointment.starts_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_query = (
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.is_deleted.is_(True), Appointment.owner_id == owner_id)
        )
        rows = await self.session.scalars(query)
        total = await self.session.scalar(count_query)
        return list(rows), int(total or 0)

    async def is_slot_booked(self, starts_at: datetime, exclude_id: UUID | None = None) -> bool:
        query = (
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.starts_at == starts_at,
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.is_deleted.is_(False),
            )
        )
        if exclude_id is not None:
            query = query.where(Appointment.id != exclude_id)
        count = await self.session.scalar(query)
        return bool(count and count > 0)

    async def booked_starts_between(
        self,
        start: datetime,
        end: datetime,
    ) -> set[datetime]:
        rows = await self.session.scalars(
            select(Appointment.starts_at).where(
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.is_deleted.is_(False),
                Appointment.starts_at >= start,
                Appointment.starts_at < end,
            )
        )
        return set(rows)

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if ACTIVE_SLOT_CONSTRAINT in str(exc.orig):
                raise SlotAlreadyBooked("This slot already has an active booking") from exc
            raise

    async def refresh(self, appointment: Appointment) -> None:
        await self.session.refresh(appointment)
