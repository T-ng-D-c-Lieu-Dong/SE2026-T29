from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentList,
    AppointmentRead,
    SlotRead,
)
from app.schemas.draft import DraftRead, DraftSave

__all__ = [
    "AppointmentCreate",
    "AppointmentList",
    "AppointmentRead",
    "DraftRead",
    "DraftSave",
    "SlotRead",
]
