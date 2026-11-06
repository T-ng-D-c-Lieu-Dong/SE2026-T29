from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AppointmentDraft(Base):
    """Autosaved, not-yet-submitted booking form (VT-115).

    ``revision`` is a client-side, monotonically increasing counter. It is the only
    ordering key: a write is applied only if its revision is strictly greater than the
    stored one. ``updated_at`` is informational and never used for ordering.
    """

    __tablename__ = "appointment_drafts"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_appointment_drafts_revision"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(100))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
