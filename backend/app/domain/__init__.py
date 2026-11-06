from app.domain.errors import (
    AppointmentNotFound,
    DraftNotFound,
    InvalidSlot,
    SlotAlreadyBooked,
    StaleDraftRevision,
)

__all__ = [
    "AppointmentNotFound",
    "DraftNotFound",
    "InvalidSlot",
    "SlotAlreadyBooked",
    "StaleDraftRevision",
]
