from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.domain import AppointmentNotFound, InvalidSlot, SlotAlreadyBooked
from app.repositories import AppointmentRepository
from app.schemas import (
    AppointmentCreate,
    AppointmentCreated,
    AppointmentList,
    AppointmentRead,
    NotificationStatus,
)
from app.services import BookingFaultInjector, BookingService, InjectedBookingFault
from app.services.notifications import BookingNotifier, NotificationOutcome
from app.telemetry import TelemetryRuntime

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

NOTIFICATION_STATUS: dict[NotificationOutcome, NotificationStatus] = {
    NotificationOutcome.DELIVERED: "sent",
    NotificationOutcome.FAILED: "failed",
    NotificationOutcome.TIMED_OUT: "timeout",
}


def get_telemetry_runtime(request: Request) -> TelemetryRuntime:
    return request.app.state.telemetry


TelemetryDependency = Annotated[TelemetryRuntime, Depends(get_telemetry_runtime)]


def get_booking_notifier(request: Request) -> BookingNotifier:
    return request.app.state.booking_notifier


NotifierDependency = Annotated[BookingNotifier, Depends(get_booking_notifier)]


def booking_service(
    session: AsyncSession,
    telemetry: TelemetryRuntime,
    notifier: BookingNotifier | None = None,
) -> BookingService:
    settings = get_settings()
    return BookingService(
        AppointmentRepository(session),
        fault_injector=BookingFaultInjector.from_settings(settings),
        telemetry=telemetry,
        notifier=notifier,
        notification_timeout_seconds=settings.notification_timeout_seconds,
    )


@router.post("", response_model=AppointmentCreated, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    session: SessionDependency,
    telemetry: TelemetryDependency,
    notifier: NotifierDependency,
) -> AppointmentCreated:
    try:
        created = await booking_service(session, telemetry, notifier).create_and_notify(
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
    appointment = AppointmentRead.model_validate(created.appointment)
    return AppointmentCreated(
        **appointment.model_dump(),
        notification_status=NOTIFICATION_STATUS[created.notification],
    )


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
