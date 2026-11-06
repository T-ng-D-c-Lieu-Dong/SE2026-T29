from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Largest integer a browser can send exactly (Number.MAX_SAFE_INTEGER).
MAX_REVISION = 2**53 - 1


class DraftSave(BaseModel):
    """Full snapshot of the booking form. Each autosave replaces the whole draft."""

    revision: int = Field(ge=1, le=MAX_REVISION)
    customer_name: str | None = Field(default=None, max_length=100)
    starts_at: datetime | None = None

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("starts_at must include a UTC offset")
        return value


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    revision: int
    customer_name: str | None
    starts_at: datetime | None
    updated_at: datetime
