from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.domain import AccessDeniedError, AppointmentNotFound, InvalidSlot, SlotAlreadyBooked
from app.repositories import AppointmentRepository
from app.schemas import AppointmentCreate, AppointmentList, AppointmentRead
from app.services import BookingFaultInjector, BookingService, InjectedBookingFault
from app.telemetry import TelemetryRuntime

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_telemetry_runtime(request: Request) -> TelemetryRuntime:
    return request.app.state.telemetry


TelemetryDependency = Annotated[TelemetryRuntime, Depends(get_telemetry_runtime)]


def require_authenticated_caller(
    caller_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    if not caller_id or not caller_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: X-User-Id header is missing or empty",
        )
    return caller_id.strip()


AuthenticatedCallerDependency = Annotated[str, Depends(require_authenticated_caller)]


def booking_service(session: AsyncSession, telemetry: TelemetryRuntime) -> BookingService:
    return BookingService(
        AppointmentRepository(session),
        fault_injector=BookingFaultInjector.from_settings(get_settings()),
        telemetry=telemetry,
    )


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    session: SessionDependency,
    telemetry: TelemetryDependency,
    caller_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> AppointmentRead:
    effective_owner = caller_id.strip() if caller_id and caller_id.strip() else (payload.owner_id or payload.customer_name)
    try:
        appointment = await booking_service(session, telemetry).create(
            customer_name=payload.customer_name,
            starts_at=payload.starts_at,
            owner_id=effective_owner,
        )
    except InvalidSlot as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SlotAlreadyBooked as exc:
        telemetry.record_booking_conflict()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InjectedBookingFault as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return AppointmentRead.model_validate(appointment)


@router.get("", response_model=AppointmentList)
async def list_appointments(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    caller_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> AppointmentList:
    appointments, total = await BookingService(AppointmentRepository(session)).list(
        limit,
        offset,
        owner_id=caller_id.strip() if caller_id and caller_id.strip() else None,
    )
    return AppointmentList(
        items=[AppointmentRead.model_validate(item) for item in appointments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/trash", response_model=AppointmentList)
async def list_trash(
    session: SessionDependency,
    telemetry: TelemetryDependency,
    caller_id: AuthenticatedCallerDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AppointmentList:
    appointments, total = await booking_service(session, telemetry).list_trash(
        caller_id=caller_id,
        limit=limit,
        offset=offset,
    )
    return AppointmentList(
        items=[AppointmentRead.model_validate(item) for item in appointments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(
    appointment_id: UUID,
    session: SessionDependency,
    telemetry: TelemetryDependency,
    caller_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> AppointmentRead:
    try:
        appointment = await booking_service(session, telemetry).get(
            appointment_id,
            caller_id=caller_id.strip() if caller_id and caller_id.strip() else None,
        )
    except AppointmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.patch("/{appointment_id}/soft-delete", response_model=AppointmentRead)
async def soft_delete_appointment(
    appointment_id: UUID,
    session: SessionDependency,
    telemetry: TelemetryDependency,
    caller_id: AuthenticatedCallerDependency,
) -> AppointmentRead:
    try:
        appointment = await booking_service(session, telemetry).soft_delete(
            appointment_id,
            caller_id=caller_id,
        )
    except AppointmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.patch("/{appointment_id}/restore", response_model=AppointmentRead)
async def restore_appointment(
    appointment_id: UUID,
    session: SessionDependency,
    telemetry: TelemetryDependency,
    caller_id: AuthenticatedCallerDependency,
) -> AppointmentRead:
    try:
        appointment = await booking_service(session, telemetry).restore(
            appointment_id,
            caller_id=caller_id,
        )
    except AppointmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except SlotAlreadyBooked as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidSlot as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_appointment(
    appointment_id: UUID,
    session: SessionDependency,
    telemetry: TelemetryDependency,
    caller_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> Response:
    try:
        await booking_service(session, telemetry).cancel(appointment_id, caller_id=caller_id)
    except AppointmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)

