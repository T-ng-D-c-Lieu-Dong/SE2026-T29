"""Notifications for booking business events (VT-118).

The channel is an unreliable external dependency. ``notify_appointment_created`` bounds it with a
time budget and turns every ``Exception`` into a ``NotificationOutcome``, so it can never fail a
booking. ``asyncio.CancelledError`` is not caught: shutdown and client disconnects still work.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

APPOINTMENT_CREATED = "appointment.created"
NOTIFICATION_LOGGER_NAME = "booking.notifications"
DEFAULT_NOTIFICATION_TIMEOUT_SECONDS = 0.5


class NotificationOutcome(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class AppointmentCreatedEvent:
    appointment_id: UUID
    customer_name: str
    starts_at: datetime
    event_type: str = APPOINTMENT_CREATED


class BookingNotifier(Protocol):
    """A channel must be non-blocking async code: the timeout cannot stop a blocked loop."""

    async def send(self, event: AppointmentCreatedEvent) -> None: ...


class LoggingBookingNotifier:
    """Default channel: one log line per event, without the customer's name."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(NOTIFICATION_LOGGER_NAME)

    async def send(self, event: AppointmentCreatedEvent) -> None:
        self.logger.info(
            "%s appointment_id=%s starts_at=%s",
            event.event_type,
            event.appointment_id,
            event.starts_at.isoformat(),
        )


async def notify_appointment_created(
    notifier: BookingNotifier,
    appointment: Any,
    *,
    timeout_seconds: float,
    logger: logging.Logger | None = None,
) -> NotificationOutcome:
    """Send ``appointment.created`` once. Raises nothing except ``asyncio.CancelledError``."""
    log = logger or logging.getLogger(NOTIFICATION_LOGGER_NAME)
    appointment_id = getattr(appointment, "id", None)
    budget = asyncio.timeout(timeout_seconds)
    try:
        # Mapping runs after the booking is committed, so it is guarded like the send (review F2).
        event = AppointmentCreatedEvent(
            appointment_id=appointment.id,
            customer_name=appointment.customer_name,
            starts_at=appointment.starts_at.astimezone(UTC),
        )
        async with budget:
            await notifier.send(event)
    except Exception as exc:
        # expired() tells our own budget apart from a TimeoutError raised by the channel itself.
        if budget.expired():
            log.warning(
                "booking.notification.timed_out appointment_id=%s timeout_seconds=%s",
                appointment_id,
                timeout_seconds,
            )
            return NotificationOutcome.TIMED_OUT
        # Only the error class: the exception message may contain customer data (NFR3).
        log.warning(
            "booking.notification.failed appointment_id=%s error=%s",
            appointment_id,
            type(exc).__name__,
        )
        return NotificationOutcome.FAILED
    return NotificationOutcome.DELIVERED
