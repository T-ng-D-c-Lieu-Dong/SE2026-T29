from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from threading import Lock
from time import time
from typing import Any

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import Counter, Meter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import Span, Tracer
from sqlalchemy.engine import Engine

from app.request_logging import REQUEST_LOGGER_NAME
from app.telemetry.config import TelemetryConfig

INSTRUMENTATION_SCOPE = "booking-api"
REDACTED_URL = "[redacted]"


@dataclass(slots=True)
class TelemetryRuntime:
    """Handles custom business telemetry and owns SDK shutdown lifecycle."""

    tracer: Tracer
    meter: Meter
    booking_conflicts: Counter
    deployment_timestamp: Any
    resource: Resource
    enabled: bool
    tracer_provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None
    logger_provider: LoggerProvider | None = None
    log_handler: logging.Handler | None = None
    log_handler_logger: logging.Logger | None = None
    application: FastAPI | None = None
    sqlalchemy_instrumentor: SQLAlchemyInstrumentor | None = None
    _closed: bool = field(default=False, init=False)
    _shutdown_lock: Any = field(default_factory=Lock, init=False, repr=False)

    def booking_span(
        self,
        operation: str,
        *,
        attributes: dict[str, str | int | float | bool] | None = None,
    ) -> AbstractContextManager[Span]:
        """Create a low-cardinality span such as ``booking.create`` or ``booking.cancel``."""

        if operation not in {"create", "cancel", "soft_delete", "restore"}:
            raise ValueError("booking operation must be 'create', 'cancel', 'soft_delete', or 'restore'")
        return self.tracer.start_as_current_span(
            f"booking.{operation}",
            attributes=attributes,
        )

    def record_booking_conflict(self) -> None:
        """Count an HTTP 409 booking conflict without customer-specific labels."""

        self.booking_conflicts.add(1)

    def shutdown(self) -> None:
        with self._shutdown_lock:
            if self._closed:
                return
            self._closed = True
        cleanup_error: Exception | None = None

        def attempt(action: Callable[[], object]) -> None:
            nonlocal cleanup_error
            try:
                action()
            except Exception as exc:  # pragma: no cover - defensive SDK cleanup
                if cleanup_error is None:
                    cleanup_error = exc

        try:
            if self.application is not None:
                attempt(lambda: FastAPIInstrumentor.uninstrument_app(self.application))
            if (
                self.sqlalchemy_instrumentor is not None
                and self.sqlalchemy_instrumentor.is_instrumented_by_opentelemetry
            ):
                attempt(self.sqlalchemy_instrumentor.uninstrument)
            if self.log_handler is not None and self.log_handler_logger is not None:
                attempt(lambda: self.log_handler_logger.removeHandler(self.log_handler))

            # Flush every bounded background pipeline during graceful shutdown.
            if self.logger_provider is not None:
                attempt(self.logger_provider.shutdown)
            if self.meter_provider is not None:
                attempt(self.meter_provider.shutdown)
            if self.tracer_provider is not None:
                attempt(self.tracer_provider.shutdown)
        finally:
            _release_runtime(self)

        if cleanup_error is not None:
            raise cleanup_error


_RUNTIME_LOCK = Lock()
_RUNTIME_RESERVED = object()
_ACTIVE_RUNTIME: TelemetryRuntime | object | None = None


def _reserve_runtime() -> None:
    global _ACTIVE_RUNTIME
    with _RUNTIME_LOCK:
        if _ACTIVE_RUNTIME is not None:
            raise RuntimeError("Only one telemetry-enabled runtime may be active in a process")
        _ACTIVE_RUNTIME = _RUNTIME_RESERVED


def _activate_runtime(runtime: TelemetryRuntime) -> None:
    global _ACTIVE_RUNTIME
    with _RUNTIME_LOCK:
        if _ACTIVE_RUNTIME is not _RUNTIME_RESERVED:
            raise RuntimeError("Telemetry runtime reservation was lost")
        _ACTIVE_RUNTIME = runtime


def _cancel_runtime_reservation() -> None:
    global _ACTIVE_RUNTIME
    with _RUNTIME_LOCK:
        if _ACTIVE_RUNTIME is _RUNTIME_RESERVED:
            _ACTIVE_RUNTIME = None


def _release_runtime(runtime: TelemetryRuntime) -> None:
    global _ACTIVE_RUNTIME
    with _RUNTIME_LOCK:
        if _ACTIVE_RUNTIME is runtime:
            _ACTIVE_RUNTIME = None


def _otlp_exporter_options(config: TelemetryConfig) -> dict[str, Any]:
    return {
        "endpoint": config.otlp_endpoint,
        "insecure": config.otlp_insecure,
        "timeout": config.exporter_timeout_millis / 1_000,
    }


def _sanitize_server_span(span: Span, _scope: dict[str, Any]) -> None:
    """Keep request URLs and query strings out of exported server spans."""

    if span is None or not span.is_recording():
        return
    for attribute in ("url.full", "url.path", "http.url", "http.target"):
        span.set_attribute(attribute, REDACTED_URL)
    span.set_attribute("url.query", "")


def _build_tracer_provider(
    config: TelemetryConfig,
    resource: Resource,
    exporter: SpanExporter,
) -> TracerProvider:
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            exporter,
            max_queue_size=config.max_queue_size,
            max_export_batch_size=config.max_export_batch_size,
            schedule_delay_millis=config.schedule_delay_millis,
            export_timeout_millis=config.exporter_timeout_millis,
        )
    )
    return provider


def _build_meter_provider(
    config: TelemetryConfig,
    resource: Resource,
    exporter: MetricExporter | None,
    metric_reader: MetricReader | None,
) -> MeterProvider:
    if metric_reader is not None:
        reader = metric_reader
    else:
        if exporter is None:
            raise ValueError("A metric exporter is required without a metric reader")
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=config.metric_export_interval_millis,
            export_timeout_millis=config.exporter_timeout_millis,
        )
    return MeterProvider(resource=resource, metric_readers=[reader])


def _build_logger_provider(
    config: TelemetryConfig,
    resource: Resource,
    exporter: LogExporter,
) -> tuple[LoggerProvider, logging.Handler]:
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            exporter,
            max_queue_size=config.max_queue_size,
            max_export_batch_size=config.max_export_batch_size,
            schedule_delay_millis=config.schedule_delay_millis,
            export_timeout_millis=config.exporter_timeout_millis,
        )
    )
    return provider, LoggingHandler(level=logging.NOTSET, logger_provider=provider)


def configure_telemetry(
    config: TelemetryConfig,
    *,
    application: FastAPI | None = None,
    engine: Engine | None = None,
    span_exporter: SpanExporter | None = None,
    metric_exporter: MetricExporter | None = None,
    metric_reader: MetricReader | None = None,
    log_exporter: LogExporter | None = None,
    log_handler_logger: logging.Logger | None = None,
) -> TelemetryRuntime:
    """Configure isolated OTel providers; no network call occurs on the request path.

    Exporter parameters are dependency-injection hooks for deterministic tests. Production
    callers normally omit them and use the configured OTLP endpoint.
    """

    resource = Resource.create(config.resource_attributes)
    if not config.enabled:
        tracer = trace.NoOpTracerProvider().get_tracer(INSTRUMENTATION_SCOPE)
        meter = metrics.NoOpMeterProvider().get_meter(INSTRUMENTATION_SCOPE)
        deployment_timestamp = meter.create_gauge(
            "booking.deployment.timestamp",
            unit="s",
            description="Unix timestamp when this Booking API process started",
        )
        deployment_timestamp.set(int(time()))
        return TelemetryRuntime(
            tracer=tracer,
            meter=meter,
            booking_conflicts=meter.create_counter(
                "booking_conflicts_total",
                unit="{conflict}",
                description="Number of booking attempts rejected with HTTP 409",
            ),
            deployment_timestamp=deployment_timestamp,
            resource=resource,
            enabled=False,
        )

    _reserve_runtime()
    try:
        return _configure_enabled_telemetry(
            config,
            resource=resource,
            application=application,
            engine=engine,
            span_exporter=span_exporter,
            metric_exporter=metric_exporter,
            metric_reader=metric_reader,
            log_exporter=log_exporter,
            log_handler_logger=log_handler_logger,
        )
    except Exception:
        _cancel_runtime_reservation()
        raise


def _configure_enabled_telemetry(
    config: TelemetryConfig,
    *,
    resource: Resource,
    application: FastAPI | None,
    engine: Engine | None,
    span_exporter: SpanExporter | None,
    metric_exporter: MetricExporter | None,
    metric_reader: MetricReader | None,
    log_exporter: LogExporter | None,
    log_handler_logger: logging.Logger | None,
) -> TelemetryRuntime:
    if engine is not None:
        sqlalchemy_instrumentor = SQLAlchemyInstrumentor()
        if sqlalchemy_instrumentor.is_instrumented_by_opentelemetry:
            raise RuntimeError(
                "SQLAlchemy is already instrumented; configure one telemetry runtime per process"
            )
    else:
        sqlalchemy_instrumentor = None

    exporter_options = _otlp_exporter_options(config)
    actual_span_exporter = span_exporter or OTLPSpanExporter(**exporter_options)
    actual_metric_exporter = metric_exporter
    if metric_reader is None and actual_metric_exporter is None:
        actual_metric_exporter = OTLPMetricExporter(**exporter_options)
    tracer_provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None
    try:
        tracer_provider = _build_tracer_provider(config, resource, actual_span_exporter)
        meter_provider = _build_meter_provider(
            config,
            resource,
            actual_metric_exporter,
            metric_reader,
        )
    except Exception:
        # Provider construction can fail before a TelemetryRuntime exists; close any
        # background pipeline that was already created, then preserve the root error.
        if meter_provider is not None:
            try:
                meter_provider.shutdown()
            except Exception:  # pragma: no cover - defensive SDK cleanup
                pass
        if tracer_provider is not None:
            try:
                tracer_provider.shutdown()
            except Exception:  # pragma: no cover - defensive SDK cleanup
                pass
        raise
    tracer = tracer_provider.get_tracer(INSTRUMENTATION_SCOPE)
    meter = meter_provider.get_meter(INSTRUMENTATION_SCOPE)
    deployment_timestamp = meter.create_gauge(
        "booking.deployment.timestamp",
        unit="s",
        description="Unix timestamp when this Booking API process started",
    )
    deployment_timestamp.set(int(time()))
    runtime = TelemetryRuntime(
        tracer=tracer,
        meter=meter,
        booking_conflicts=meter.create_counter(
            "booking_conflicts_total",
            unit="{conflict}",
            description="Number of booking attempts rejected with HTTP 409",
        ),
        deployment_timestamp=deployment_timestamp,
        resource=resource,
        enabled=True,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        application=application,
    )

    try:
        if application is not None:
            FastAPIInstrumentor.instrument_app(
                application,
                tracer_provider=tracer_provider,
                meter_provider=meter_provider,
                server_request_hook=_sanitize_server_span,
            )
        if engine is not None and sqlalchemy_instrumentor is not None:
            runtime.sqlalchemy_instrumentor = sqlalchemy_instrumentor
            runtime.sqlalchemy_instrumentor.instrument(
                engine=engine,
                tracer_provider=tracer_provider,
                meter_provider=meter_provider,
            )
        if config.export_logs:
            actual_log_exporter = log_exporter or OTLPLogExporter(**exporter_options)
            runtime.logger_provider, runtime.log_handler = _build_logger_provider(
                config,
                resource,
                actual_log_exporter,
            )
            runtime.log_handler_logger = log_handler_logger or logging.getLogger(
                REQUEST_LOGGER_NAME
            )
            runtime.log_handler_logger.addHandler(runtime.log_handler)

        _activate_runtime(runtime)
        return runtime
    except Exception:
        runtime.shutdown()
        raise
