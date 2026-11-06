from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain import DraftNotFound, StaleDraftRevision
from app.models import AppointmentDraft
from app.repositories import DraftRepository


class DraftService:
    def __init__(self, repository: DraftRepository) -> None:
        self.repository = repository

    async def save(
        self,
        draft_id: UUID,
        revision: int,
        customer_name: str | None,
        starts_at: datetime | None,
    ) -> AppointmentDraft:
        saved = await self.repository.save_if_newer(draft_id, revision, customer_name, starts_at)
        if saved is None:
            raise StaleDraftRevision(await self.get(draft_id))
        return saved

    async def get(self, draft_id: UUID) -> AppointmentDraft:
        draft = await self.repository.get(draft_id)
        if draft is None:
            raise DraftNotFound("Draft was not found")
        return draft
