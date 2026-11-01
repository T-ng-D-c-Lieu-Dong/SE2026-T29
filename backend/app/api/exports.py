from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.domain import ExportForbidden, ExportUnauthenticated, InvalidExportRange
from app.repositories import AppointmentRepository
from app.services.export import (
    authenticate,
    authorize_scope,
    parse_api_keys,
    render_csv,
    require_export_role,
    resolve_window,
)

router = APIRouter(prefix="/api/exports", tags=["exports"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def export_role(x_api_key: Annotated[str | None, Header()] = None) -> str:
    try:
        role = authenticate(x_api_key, parse_api_keys(get_settings().export_api_keys))
        require_export_role(role)
    except ExportUnauthenticated as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExportForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return role


RoleDependency = Annotated[str, Depends(export_role)]


@router.get("/appointments")
async def export_appointments(
    session: SessionDependency,
    role: RoleDependency,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    include_cancelled: bool = False,
) -> Response:
    try:
        start, end = resolve_window(date_from, date_to)
        authorize_scope(role, include_cancelled)
    except InvalidExportRange as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExportForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        rows = await AppointmentRepository(session).export_between(start, end, include_cancelled)
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="Export is temporarily unavailable") from exc

    return Response(
        content=render_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="appointments_{date_from}_{date_to}.csv"'
            ),
            "Cache-Control": "no-store",
        },
    )
