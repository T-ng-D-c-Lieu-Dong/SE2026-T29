from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import appointments, drafts, health, slots, version
from app.config import get_settings
from app.db import engine
from app.request_logging import (
    REQUEST_LOGGER_NAME,
    configure_request_logger,
    install_request_logging,
)
from app.telemetry import TelemetryConfig, configure_telemetry


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        application.state.telemetry.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Production Readiness Booking API",
        version="0.1.0",
        lifespan=lifespan,
    )
    request_logger = configure_request_logger(
        logger_name=f"{REQUEST_LOGGER_NAME}.{id(application):x}"
    )
    telemetry = configure_telemetry(
        TelemetryConfig(
            enabled=settings.telemetry_enabled,
            service_name=settings.service_name,
            release=settings.release,
            deployment_environment=settings.deployment_environment,
            commit_sha=settings.commit_sha,
            otlp_endpoint=settings.otlp_endpoint,
            otlp_insecure=settings.otlp_insecure,
            exporter_timeout_millis=settings.telemetry_exporter_timeout_millis,
            max_queue_size=settings.telemetry_max_queue_size,
            max_export_batch_size=settings.telemetry_max_export_batch_size,
            schedule_delay_millis=settings.telemetry_schedule_delay_millis,
            metric_export_interval_millis=settings.telemetry_metric_export_interval_millis,
            export_logs=settings.telemetry_export_logs,
        ),
        application=application,
        engine=engine.sync_engine,
        log_handler_logger=request_logger,
    )
    application.state.telemetry = telemetry
    install_request_logging(
        application,
        release=settings.release,
        commit_sha=settings.commit_sha,
        logger=request_logger,
    )
    application.include_router(health.router)
    application.include_router(version.router)
    application.include_router(slots.router)
    application.include_router(appointments.router)
    application.include_router(drafts.router)
    return application


app = create_app()
