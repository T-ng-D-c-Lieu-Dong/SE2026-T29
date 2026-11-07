from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.domain import AppointmentNotFound, InvalidSlot, SlotAlreadyBooked
from app.repositories import AppointmentRepository
from app.schemas import AppointmentCreate, AppointmentList, AppointmentRead
from app.services import BookingFaultInjector, BookingService, InjectedBookingFault
from app.services.notifications import BookingNotifier, LoggingBookingNotifier
from app.telemetry import TelemetryRuntime

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_telemetry_runtime(request: Request) -> TelemetryRuntime:
    return request.app.state.telemetry


TelemetryDependency = Annotated[TelemetryRuntime, Depends(get_telemetry_runtime)]


def get_booking_notifier(request: Request) -> BookingNotifier:
    # STUB (VT-118): dependency exists so tests can override it; not used by any route yet.
    return getattr(request.app.state, "booking_notifier", None) or LoggingBookingNotifier()


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
) -> AppointmentRead:
    try:
        appointment = await booking_service(session, telemetry).create(
            payload.customer_name,
            payload.starts_at,
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
) -> AppointmentList:
    appointments, total = await BookingService(AppointmentRepository(session)).list(limit, offset)
    return AppointmentList(
        items=[AppointmentRead.model_validate(item) for item in appointments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_appointment(
    appointment_id: UUID,
    session: SessionDependency,
    telemetry: TelemetryDependency,
) -> Response:
    try:
        await booking_service(session, telemetry).cancel(appointment_id)
    except AppointmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
