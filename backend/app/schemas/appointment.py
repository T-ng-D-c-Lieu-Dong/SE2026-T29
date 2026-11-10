from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    starts_at: datetime

    @field_validator("customer_name")
    @classmethod
    def normalize_customer_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("customer_name must not be blank")
        return normalized

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a UTC offset")
        return value


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_name: str
    starts_at: datetime
    status: Literal["booked", "cancelled"]
    created_at: datetime
    cancelled_at: datetime | None


NotificationStatus = Literal["sent", "failed", "timeout"]


class AppointmentCreated(AppointmentRead):
    notification_status: NotificationStatus


class AppointmentList(BaseModel):
    items: list[AppointmentRead]
    total: int
    limit: int
    offset: int


class SlotRead(BaseModel):
    starts_at: datetime
