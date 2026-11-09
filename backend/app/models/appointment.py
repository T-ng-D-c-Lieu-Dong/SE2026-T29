from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    CANCELLED = "cancelled"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'cancelled')",
            name="ck_appointments_status",
        ),
        Index(
            "uq_appointments_active_starts_at",
            "starts_at",
            unique=True,
            postgresql_where=text("status = 'booked' AND is_deleted = false"),
        ),
        Index("ix_appointments_starts_at", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AppointmentStatus.BOOKED.value,
        server_default=text("'booked'"),
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
