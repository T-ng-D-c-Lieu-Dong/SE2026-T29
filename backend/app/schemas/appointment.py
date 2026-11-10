from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    starts_at: datetime
    owner_id: str | None = Field(default=None, max_length=100)

    @field_validator("customer_name")
    def normalize_customer_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("customer_name must not be blank")
        return normalized

    @field_validator("starts_at")
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a UTC offset")
        return value


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_name: str
    owner_id: str = "anonymous"
    starts_at: datetime
    status: Literal["booked", "cancelled"]
    is_deleted: bool = False
    created_at: datetime
    cancelled_at: datetime | None = None
    deleted_at: datetime | None = None


class AppointmentList(BaseModel):
    items: list[AppointmentRead]
    total: int
    limit: int
    offset: int


class SlotRead(BaseModel):
    starts_at: datetime
