from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.domain import DraftNotFound, StaleDraftRevision
from app.repositories import DraftRepository
from app.schemas import DraftRead, DraftSave
from app.services.drafts import DraftService

router = APIRouter(prefix="/api/drafts", tags=["drafts"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.put("/{draft_id}", response_model=DraftRead)
async def save_draft(draft_id: UUID, payload: DraftSave, session: SessionDependency) -> DraftRead:
    try:
        saved = await DraftService(DraftRepository(session)).save(
            draft_id, payload.revision, payload.customer_name, payload.starts_at
        )
    except StaleDraftRevision as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "current": DraftRead.model_validate(exc.current).model_dump(mode="json"),
            },
        ) from exc
    return DraftRead.model_validate(saved)


@router.get("/{draft_id}", response_model=DraftRead)
async def get_draft(draft_id: UUID, session: SessionDependency) -> DraftRead:
    try:
        draft = await DraftService(DraftRepository(session)).get(draft_id)
    except DraftNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DraftRead.model_validate(draft)
