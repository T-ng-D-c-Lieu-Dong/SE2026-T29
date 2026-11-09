from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domain import (
    AccessDeniedError,
    SlotAlreadyBooked,
)
from app.models import Appointment, AppointmentStatus
from app.services.booking import BookingService

BOOKING_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


class InMemoryAppointmentRepository:
    def __init__(self) -> None:
        self.items: dict[uuid4, Appointment] = {}

    async def get(self, appointment_id, include_deleted: bool = False):
        item = self.items.get(appointment_id)
        if item is None:
            return None
        if getattr(item, "is_deleted", False) and not include_deleted:
            return None
        return item

    async def get_raw(self, appointment_id):
        return self.items.get(appointment_id)

    async def booked_starts_between(self, start, end):
        return {
            item.starts_at
            for item in self.items.values()
            if item.status == AppointmentStatus.BOOKED.value
            and not getattr(item, "is_deleted", False)
            and start <= item.starts_at < end
        }

    async def commit(self) -> None:
        pass

    async def refresh(self, appointment) -> None:
        pass


def make_service(items: dict, now_dt: datetime) -> BookingService:
    repo = InMemoryAppointmentRepository()
    repo.items = items
    return BookingService(repository=repo, now_provider=lambda: now_dt)


@pytest.mark.unit
async def test_unit_soft_delete_success():
    now_dt = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    apt_id = uuid4()
    apt = Appointment(
        id=apt_id,
        customer_name="UserA",
        starts_at=now_dt + timedelta(days=1),
        status=AppointmentStatus.BOOKED.value,
        owner_id="UserA",
        is_deleted=False,
    )
    service = make_service({apt_id: apt}, now_dt)

    updated = await service.soft_delete(apt_id, caller_id="UserA")
    assert updated.is_deleted is True
    assert updated.deleted_at is not None


@pytest.mark.unit
async def test_unit_soft_delete_unauthorized():
    now_dt = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    apt_id = uuid4()
    apt = Appointment(
        id=apt_id,
        customer_name="UserA",
        starts_at=now_dt + timedelta(days=1),
        status=AppointmentStatus.BOOKED.value,
        owner_id="UserA",
        is_deleted=False,
    )
    service = make_service({apt_id: apt}, now_dt)

    with pytest.raises(AccessDeniedError):
        await service.soft_delete(apt_id, caller_id="UserB")


@pytest.mark.unit
async def test_unit_restore_success():
    now_dt = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    apt_id = uuid4()
    apt = Appointment(
        id=apt_id,
        customer_name="UserA",
        starts_at=now_dt + timedelta(days=1),
        status=AppointmentStatus.BOOKED.value,
        owner_id="UserA",
        is_deleted=True,
        deleted_at=now_dt - timedelta(hours=1),
    )
    service = make_service({apt_id: apt}, now_dt)

    restored = await service.restore(apt_id, caller_id="UserA")
    assert restored.is_deleted is False
    assert restored.deleted_at is None


@pytest.mark.unit
async def test_unit_restore_conflict_when_slot_rebooked():
    now_dt = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    slot_time = now_dt + timedelta(days=1)
    apt_a_id = uuid4()
    apt_a = Appointment(
        id=apt_a_id,
        customer_name="UserA",
        starts_at=slot_time,
        status=AppointmentStatus.BOOKED.value,
        owner_id="UserA",
        is_deleted=True,
    )
    apt_b_id = uuid4()
    apt_b = Appointment(
        id=apt_b_id,
        customer_name="UserB",
        starts_at=slot_time,
        status=AppointmentStatus.BOOKED.value,
        owner_id="UserB",
        is_deleted=False,
    )
    service = make_service({apt_a_id: apt_a, apt_b_id: apt_b}, now_dt)

    with pytest.raises(SlotAlreadyBooked):
        await service.restore(apt_a_id, caller_id="UserA")
