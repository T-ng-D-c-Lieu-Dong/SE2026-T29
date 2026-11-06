from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppointmentDraft


class DraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_if_newer(
        self,
        draft_id: UUID,
        revision: int,
        customer_name: str | None,
        starts_at: datetime | None,
    ) -> AppointmentDraft | None:
        """Atomic compare-and-set in one statement.

        Inserts the draft, or overwrites it only when the incoming revision is strictly
        greater than the stored one. Returns ``None`` when the write was rejected as
        stale. PostgreSQL re-evaluates the WHERE clause after waiting on a row lock, so
        two concurrent saves cannot both pass the check (no read-then-write race).
        """
        statement = insert(AppointmentDraft).values(
            id=draft_id,
            revision=revision,
            customer_name=customer_name,
            starts_at=starts_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AppointmentDraft.id],
            set_={
                "revision": statement.excluded.revision,
                "customer_name": statement.excluded.customer_name,
                "starts_at": statement.excluded.starts_at,
                "updated_at": func.now(),
            },
            where=AppointmentDraft.revision < statement.excluded.revision,
        ).returning(AppointmentDraft)
        saved = await self.session.scalar(statement, execution_options={"populate_existing": True})
        await self.session.commit()
        return saved

    async def get(self, draft_id: UUID) -> AppointmentDraft | None:
        return await self.session.get(AppointmentDraft, draft_id, populate_existing=True)
