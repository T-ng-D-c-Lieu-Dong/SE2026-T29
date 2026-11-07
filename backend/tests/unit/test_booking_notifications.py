"""VT-118 unit tests: notifying ``appointment.created`` must never break the booking.

Written before the implementation (test-first). Equivalence partitions for the notifier, one
representative per class (docs/vt118/02-test-strategy.md):

* N1 completes normally            -> ``DELIVERED``
* N2 raises an ``Exception``       -> ``FAILED`` (representative: ``ConnectionError``)
* N3 never completes within budget -> ``TIMED_OUT`` (representative: waits on an Event never set)
* N4 blocks the event loop         -> outside the async contract, residual risk (TC18, xfail)
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.domain import InvalidSlot
from app.main import create_app
from app.models import AppointmentStatus
from app.repositories import AppointmentRepository
from app.request_logging import JsonLogFormatter
from app.services.booking import BOOKING_TIMEZONE, BookingService
from app.services.fault_injection import BookingFaultInjector, InjectedBookingFault
from app.services.notifications import (
    APPOINTMENT_CREATED,
    NOTIFICATION_LOGGER_NAME,
    AppointmentCreatedEvent,
    NotificationOutcome,
    notify_appointment_created,
)

NOW = datetime(2026, 11, 7, 3, 0, tzinfo=UTC)
LOCAL_START = datetime(2026, 11, 10, 9, 30, tzinfo=BOOKING_TIMEZONE)
SECRET_NAME = "Nguyen Thi Bi Mat"


class RecordingNotifier:
    """Fake channel whose behaviour is one equivalence class (N1 ok, N2 raise, N3 hang)."""

    def __init__(self, behaviour: str = "ok", calls: list[str] | None = None) -> None:
        self.behaviour = behaviour
        self.events: list[AppointmentCreatedEvent] = []
        self.calls = calls if calls is not None else []
        self.started = asyncio.Event()

    async def send(self, event: AppointmentCreatedEvent) -> None:
        self.events.append(event)
        self.calls.append("notify")
        self.started.set()
        if self.behaviour == "raise":
            # The message deliberately contains PII: it must not reach the logs.
            raise ConnectionError(f"SMTP refused message for {event.customer_name}")
        if self.behaviour == "hang":
            await asyncio.Event().wait()


class FakeRepository:
    """Records the order of repository calls in a list shared with the notifier."""

    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.appointment: SimpleNamespace | None = None
        self.commits = 0

    async def create(self, customer_name: str, starts_at: datetime) -> SimpleNamespace:
        self.calls.append("create")
        self.appointment = SimpleNamespace(
            id=uuid4(),
            customer_name=customer_name,
            starts_at=starts_at,
            status=AppointmentStatus.BOOKED.value,
            created_at=NOW,
            cancelled_at=None,
        )
        return self.appointment

    async def refresh(self, appointment: SimpleNamespace) -> None:
        self.calls.append("refresh")

    async def commit(self) -> None:
        self.calls.append("commit")
        self.commits += 1


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def notification_log() -> Iterator[tuple[logging.Logger, ListHandler]]:
    logger = logging.getLogger(f"test.vt118.{uuid4().hex}")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    handler = ListHandler()
    logger.addHandler(handler)
    yield logger, handler
    logger.removeHandler(handler)


def booked_appointment() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        customer_name=SECRET_NAME,
        starts_at=LOCAL_START,
        status=AppointmentStatus.BOOKED.value,
        created_at=NOW,
        cancelled_at=None,
    )


def service_with(
    behaviour: str,
    calls: list[str],
    *,
    fault_injector: BookingFaultInjector | None = None,
) -> tuple[BookingService, FakeRepository, RecordingNotifier]:
    repository = FakeRepository(calls)
    notifier = RecordingNotifier(behaviour, calls)
    service = BookingService(
        cast(AppointmentRepository, repository),
        now_provider=lambda: NOW,
        fault_injector=fault_injector,
        notifier=notifier,
        notification_timeout_seconds=0.05,
    )
    return service, repository, notifier


# --- Dispatcher: one test per notifier partition -------------------------------------------


async def test_tc01_n1_delivered_event_describes_the_booking(notification_log) -> None:
    logger, _ = notification_log
    notifier = RecordingNotifier("ok")
    appointment = booked_appointment()

    outcome = await notify_appointment_created(
        notifier, appointment, timeout_seconds=1.0, logger=logger
    )

    assert outcome is NotificationOutcome.DELIVERED
    assert notifier.events == [
        AppointmentCreatedEvent(
            appointment_id=appointment.id,
            customer_name=SECRET_NAME,
            starts_at=LOCAL_START,
            event_type=APPOINTMENT_CREATED,
        )
    ]
    assert notifier.events[0].starts_at.utcoffset() == timedelta(0)


async def test_tc02_n2_raising_channel_is_reported_and_logged_without_pii(
    notification_log,
) -> None:
    logger, handler = notification_log
    notifier = RecordingNotifier("raise")
    appointment = booked_appointment()

    outcome = await notify_appointment_created(
        notifier, appointment, timeout_seconds=1.0, logger=logger
    )

    assert outcome is NotificationOutcome.FAILED
    assert len(notifier.events) == 1
    messages = [record.getMessage() for record in handler.records]
    assert any(
        "booking.notification.failed" in message
        and str(appointment.id) in message
        and "ConnectionError" in message
        for message in messages
    ), messages
    assert all(SECRET_NAME not in message for message in messages)
    assert all(record.exc_info is None for record in handler.records)


async def test_tc03_n3_hanging_channel_is_cut_at_the_timeout(notification_log) -> None:
    logger, handler = notification_log
    notifier = RecordingNotifier("hang")

    started = time.perf_counter()
    outcome = await notify_appointment_created(
        notifier, booked_appointment(), timeout_seconds=0.05, logger=logger
    )
    elapsed = time.perf_counter() - started

    assert outcome is NotificationOutcome.TIMED_OUT
    assert notifier.started.is_set()
    assert elapsed < 1.0
    assert any("booking.notification.timed_out" in r.getMessage() for r in handler.records)


async def test_tc07_outer_cancellation_is_propagated_not_reported_as_failure() -> None:
    notifier = RecordingNotifier("hang")
    task = asyncio.create_task(
        notify_appointment_created(notifier, booked_appointment(), timeout_seconds=30.0)
    )
    await asyncio.wait_for(notifier.started.wait(), timeout=1.0)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


# --- Added after reviewing the AI patch (review findings F1, F2) -----------------------------


async def test_tc20_error_while_mapping_the_event_is_contained(notification_log) -> None:
    """F2: building the event runs after commit, so a mapping error must not escape as 500."""
    logger, handler = notification_log
    broken = SimpleNamespace(id=uuid4(), customer_name="Cuong", starts_at=None)

    outcome = await notify_appointment_created(
        RecordingNotifier("ok"), broken, timeout_seconds=1.0, logger=logger
    )

    assert outcome is NotificationOutcome.FAILED
    assert any(
        "booking.notification.failed" in record.getMessage()
        and str(broken.id) in record.getMessage()
        for record in handler.records
    )


async def test_tc21_default_channel_and_failures_are_visible_as_json_lines() -> None:
    """F1: the production default channel must emit something; INFO must not be dropped."""
    application = create_app()
    logger = logging.getLogger(NOTIFICATION_LOGGER_NAME)
    # pytest >= 9 attaches its own StreamHandler subclasses to non-propagating loggers, so select
    # the application's JSON handler explicitly instead of "any StreamHandler".
    handlers = [
        handler
        for handler in logger.handlers
        if type(handler) is logging.StreamHandler
        and isinstance(handler.formatter, JsonLogFormatter)
    ]
    assert handlers, "no JSON handler on the notification logger: INFO lines are dropped"
    assert logger.isEnabledFor(logging.INFO)
    appointment = booked_appointment()
    buffer = io.StringIO()
    previous = handlers[0].setStream(buffer)
    try:
        delivered = await notify_appointment_created(
            application.state.booking_notifier, appointment, timeout_seconds=1.0
        )
        failed = await notify_appointment_created(
            RecordingNotifier("raise"), appointment, timeout_seconds=1.0
        )
    finally:
        handlers[0].setStream(previous)

    lines = [json.loads(line) for line in buffer.getvalue().splitlines()]
    assert (delivered, failed) == (NotificationOutcome.DELIVERED, NotificationOutcome.FAILED)
    assert [line["level"] for line in lines] == ["INFO", "WARNING"]
    assert lines[0]["event"].startswith(APPOINTMENT_CREATED)
    assert lines[1]["event"].startswith("booking.notification.failed")
    assert all(str(appointment.id) in line["event"] for line in lines)
    assert SECRET_NAME not in buffer.getvalue()


# --- Service: the invariant "notification outcome never changes the booking outcome" -------


@pytest.mark.parametrize(
    ("behaviour", "expected"),
    [
        pytest.param("ok", NotificationOutcome.DELIVERED, id="N1-ok"),
        pytest.param("raise", NotificationOutcome.FAILED, id="N2-raise"),
        pytest.param("hang", NotificationOutcome.TIMED_OUT, id="N3-hang"),
    ],
)
async def test_tc04_booking_is_committed_before_notifying_and_survives_every_outcome(
    behaviour: str,
    expected: NotificationOutcome,
) -> None:
    calls: list[str] = []
    service, repository, notifier = service_with(behaviour, calls)

    created = await service.create_and_notify("Cuong", LOCAL_START)

    assert created.notification is expected
    assert created.appointment.status == AppointmentStatus.BOOKED.value
    assert repository.commits == 1
    # Commit is the last DB call before the side effect: the transaction is closed and the
    # pooled connection is released while the channel is awaited (NFR2).
    assert calls[-2:] == ["commit", "notify"], calls
    assert calls.count("notify") == 1
    assert notifier.events[0].appointment_id == created.appointment.id


async def test_tc05_invalid_slot_is_rejected_and_nothing_is_sent() -> None:
    calls: list[str] = []
    service, repository, notifier = service_with("ok", calls)

    with pytest.raises(InvalidSlot):
        await service.create_and_notify("Cuong", LOCAL_START.replace(minute=15))

    assert notifier.events == []
    assert repository.commits == 0


async def test_tc06_injected_fault_fails_booking_and_nothing_is_sent() -> None:
    calls: list[str] = []
    injector = BookingFaultInjector(
        mode="error",
        until=NOW + timedelta(hours=1),
        now_provider=lambda: NOW,
        random_provider=lambda: 0.0,
    )
    service, repository, notifier = service_with("ok", calls, fault_injector=injector)

    with pytest.raises(InjectedBookingFault):
        await service.create_and_notify("Cuong", LOCAL_START)

    assert notifier.events == []
    assert repository.commits == 0


# --- Configuration partitions for BOOKING_NOTIFICATION_TIMEOUT_SECONDS ---------------------


def test_tc17_default_notification_timeout_is_half_a_second() -> None:
    assert Settings().notification_timeout_seconds == 0.5


@pytest.mark.parametrize("seconds", [0.001, 5.0], ids=["valid-min", "valid-max"])
def test_tc17_notification_timeout_accepts_the_valid_partition(seconds: float) -> None:
    assert Settings(notification_timeout_seconds=seconds).notification_timeout_seconds == seconds


@pytest.mark.parametrize("seconds", [0.0, -1.0, 5.01, 60.0], ids=["zero", "negative", ">5", "60"])
def test_tc17_notification_timeout_rejects_invalid_partitions(seconds: float) -> None:
    with pytest.raises(ValidationError):
        Settings(notification_timeout_seconds=seconds)


# --- Residual risk, documented as an executable expectation ----------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Residual risk (plan review R7): asyncio.timeout cannot interrupt a notifier that blocks "
        "the event loop. BookingNotifier.send() must be non-blocking async code."
    ),
)
async def test_tc18_n4_blocking_channel_is_not_bounded_by_the_timeout() -> None:
    class BlockingNotifier:
        async def send(self, event: AppointmentCreatedEvent) -> None:
            time.sleep(0.3)  # noqa: ASYNC251 - deliberate: simulates requests/smtplib in async def

    started = time.perf_counter()
    outcome = await notify_appointment_created(
        BlockingNotifier(), booked_appointment(), timeout_seconds=0.05
    )

    assert outcome is NotificationOutcome.TIMED_OUT
    assert time.perf_counter() - started < 0.2
