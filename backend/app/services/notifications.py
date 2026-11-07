"""Notifications for booking business events (VT-118).

STUB — interface only, no behaviour yet: nothing is sent and every call reports ``DELIVERED``.
It exists so that the test-first suite fails on assertions about behaviour instead of ImportError.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
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
    async def send(self, event: AppointmentCreatedEvent) -> None: ...


class LoggingBookingNotifier:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(NOTIFICATION_LOGGER_NAME)

    async def send(self, event: AppointmentCreatedEvent) -> None:
        return None


async def notify_appointment_created(
    notifier: BookingNotifier,
    appointment: Any,
    *,
    timeout_seconds: float,
    logger: logging.Logger | None = None,
) -> NotificationOutcome:
    return NotificationOutcome.DELIVERED
