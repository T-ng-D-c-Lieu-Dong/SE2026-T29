"""VT-119 contract test: the in-memory fake and the real repository must agree.

Risk: a mock that silently diverges from PostgreSQL semantics (range bounds, status filter,
ordering) lets unit tests pass while production returns different data.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.models import Appointment
from app.repositories import AppointmentRepository

pytestmark = pytest.mark.integration
T0 = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)


@dataclass
class FakeRow:
    id: UUID
    customer_name: str
    starts_at: datetime
    status: str
    created_at: datetime


class FakeExportRepository:
    """Hand-written double used by unit tests; its behaviour is pinned to the real one below."""

    def __init__(self, rows: list[FakeRow]) -> None:
        self.rows = rows

    async def export_between(self, start, end, include_cancelled):
        selected = [
            r
            for r in self.rows
            if start <= r.starts_at < end and (include_cancelled or r.status == "booked")
        ]
        return sorted(selected, key=lambda r: (r.starts_at, r.created_at, r.id))


C0 = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)
# (name, starts_at, status, created_at). The two "tie-*" rows share a slot and are inserted
# in the opposite order of created_at, so only an explicit ORDER BY can sort them correctly.
SCENARIO = [
    ("before-start", T0 - timedelta(minutes=30), "booked", C0),
    ("at-start", T0, "booked", C0),
    ("inside-cancelled", T0 + timedelta(hours=1), "cancelled", C0),
    ("inside-b", T0 + timedelta(hours=3), "booked", C0),
    ("inside-a", T0 + timedelta(hours=2), "booked", C0),
    ("tie-late", T0 + timedelta(hours=5), "booked", C0 + timedelta(hours=1)),
    ("tie-early", T0 + timedelta(hours=5), "cancelled", C0),
    ("at-end", T0 + timedelta(hours=24), "booked", C0),
]


@pytest.fixture(params=["fake", "postgres"])
async def repository(request, test_session_factory):
    if request.param == "fake":
        rows = [FakeRow(uuid4(), n, s, st, c) for n, s, st, c in SCENARIO]
        yield FakeExportRepository(rows)
        return
    async with test_session_factory() as session:
        for name, starts_at, status, created_at in SCENARIO:
            session.add(
                Appointment(
                    customer_name=name,
                    starts_at=starts_at,
                    status=status,
                    created_at=created_at,
                )
            )
            await session.flush()
        await session.commit()
    async with test_session_factory() as session:
        yield AppointmentRepository(session)


@pytest.mark.parametrize(
    ("include_cancelled", "expected"),
    [
        (False, ["at-start", "inside-a", "inside-b", "tie-late"]),
        (
            True,
            ["at-start", "inside-cancelled", "inside-a", "inside-b", "tie-early", "tie-late"],
        ),
    ],
)
async def test_export_between_contract(repository, include_cancelled, expected) -> None:
    result = await repository.export_between(T0, T0 + timedelta(hours=24), include_cancelled)

    assert [r.customer_name for r in result] == expected


async def test_export_between_empty_window(repository) -> None:
    assert await repository.export_between(T0, T0, True) == []
