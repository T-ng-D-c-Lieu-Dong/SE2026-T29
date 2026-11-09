from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from app.models import AppointmentStatus
from app.request_logging import (
    REQUEST_LOGGER_NAME,
    configure_request_logger,
    install_request_logging,
)
from app.services.booking import BOOKING_TIMEZONE, BookingService
from app.telemetry import TelemetryConfig, configure_telemetry
from app.telemetry.runtime import HTTP_SERVER_DURATION_BUCKETS_SECONDS

NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)


class BookingRepositoryStub:
    def __init__(self) -> None:
        self.created = None
        self.commits = 0

    async def create(self, customer_name: str, starts_at: datetime):
        self.created = SimpleNamespace(
            id=uuid4(),
            customer_name=customer_name,
            starts_at=starts_at,
            status=AppointmentStatus.BOOKED.value,
            created_at=NOW,
            cancelled_at=None,
        )
        return self.created

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, appointment) -> None:
        return None


class BlockingFailingExporter(SpanExporter):
    """Model an unavailable Collector without touching the network."""

    def __init__(self) -> None:
        self.export_started = threading.Event()
        self.release_export = threading.Event()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        self.export_started.set()
        self.release_export.wait(timeout=1)
        return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        self.release_export.set()


def test_resource_attributes_correlate_telemetry_with_release() -> None:
    config = TelemetryConfig(
        service_name="booking-api",
        release="v0.2.0",
        deployment_environment="test",
        commit_sha="abc1234",
    )

    assert config.resource_attributes == {
        "service.name": "booking-api",
        "service.version": "v0.2.0",
        "deployment.environment": "test",
        "deployment.environment.name": "test",
        "release": "v0.2.0",
        "commit_sha": "abc1234",
    }


def test_config_rejects_unbounded_or_invalid_batch_settings() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        TelemetryConfig(max_queue_size=0)

    with pytest.raises(ValueError, match="cannot exceed"):
        TelemetryConfig(max_queue_size=8, max_export_batch_size=9)


def test_disabled_runtime_keeps_business_instrumentation_safe() -> None:
    runtime = configure_telemetry(TelemetryConfig(enabled=False))

    with runtime.booking_span("create"):
        runtime.record_booking_conflict()

    runtime.shutdown()
    runtime.shutdown()


def test_booking_span_validates_low_cardinality_operation_name() -> None:
    runtime = configure_telemetry(TelemetryConfig(enabled=False))

    with pytest.raises(ValueError, match="create.*cancel"):
        runtime.booking_span("list")


def test_http_duration_histogram_uses_explicit_buckets() -> None:
    reader = InMemoryMetricReader()
    runtime = configure_telemetry(
        TelemetryConfig(enabled=True),
        span_exporter=InMemorySpanExporter(),
        metric_reader=reader,
        log_exporter=InMemoryLogRecordExporter(),
    )

    try:
        histogram = runtime.meter.create_histogram(
            "http.server.request.duration",
            unit="s",
        )
        histogram.record(0.25, {"http.route": "/api/appointments"})
        metrics = reader.get_metrics_data().resource_metrics[0].scope_metrics[0].metrics
        metric = next(item for item in metrics if item.name == "http.server.request.duration")
        point = metric.data.data_points[0]
        assert point.explicit_bounds == HTTP_SERVER_DURATION_BUCKETS_SECONDS
    finally:
        runtime.shutdown()


def test_business_signals_share_release_resource_and_trace_context() -> None:
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    log_exporter = InMemoryLogRecordExporter()
    runtime = configure_telemetry(
        TelemetryConfig(
            enabled=True,
            release="v0.2.0",
            deployment_environment="test",
            commit_sha="abc1234",
            schedule_delay_millis=1,
        ),
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        log_exporter=log_exporter,
    )

    try:
        with runtime.booking_span("create"):
            runtime.record_booking_conflict()
            logging.getLogger(REQUEST_LOGGER_NAME).warning("correlated test log")

        assert runtime.tracer_provider is not None
        assert runtime.logger_provider is not None
        assert runtime.tracer_provider.force_flush()
        assert runtime.logger_provider.force_flush()

        booking_span = next(
            span for span in span_exporter.get_finished_spans() if span.name == "booking.create"
        )
        log_record = next(
            item.log_record
            for item in log_exporter.get_finished_logs()
            if item.log_record.body == "correlated test log"
        )
        metrics_data = metric_reader.get_metrics_data()
        metric_names = {
            metric.name
            for resource_metrics in metrics_data.resource_metrics
            for scope_metrics in resource_metrics.scope_metrics
            for metric in scope_metrics.metrics
        }

        assert booking_span.resource.attributes["service.version"] == "v0.2.0"
        assert booking_span.resource.attributes["commit_sha"] == "abc1234"
        assert log_record.trace_id == booking_span.context.trace_id
        assert "booking_conflicts_total" in metric_names
        assert "booking.deployment.timestamp" in metric_names
        assert all(
            item.resource.attributes["service.version"] == "v0.2.0"
            for item in metrics_data.resource_metrics
        )
    finally:
        runtime.shutdown()


def test_real_request_correlates_log_and_trace_without_leaking_url_data() -> None:
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    log_exporter = InMemoryLogRecordExporter()
    stream = StringIO()
    logger = configure_request_logger(
        stream=stream,
        logger_name=f"{REQUEST_LOGGER_NAME}.correlation-test",
    )
    application = FastAPI()
    runtime = configure_telemetry(
        TelemetryConfig(
            enabled=True,
            release="v0.2.0",
            deployment_environment="test",
            commit_sha="abc1234",
            schedule_delay_millis=1,
        ),
        application=application,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        log_exporter=log_exporter,
        log_handler_logger=logger,
    )
    install_request_logging(
        application,
        release="v0.2.0",
        commit_sha="abc1234",
        logger=logger,
    )

    @application.get("/appointments/{appointment_id}")
    async def appointment(appointment_id: str) -> dict[str, str]:
        return {"id": appointment_id}

    try:
        with TestClient(application) as client:
            response = client.get("/appointments/private-appointment-id?customer_name=QuerySecret")

        assert response.status_code == 200
        assert runtime.tracer_provider is not None
        assert runtime.logger_provider is not None
        assert runtime.tracer_provider.force_flush()
        assert runtime.logger_provider.force_flush()

        event = json.loads(stream.getvalue())
        spans = span_exporter.get_finished_spans()
        server_span = next(span for span in spans if span.kind is SpanKind.SERVER)
        exported_request_log = next(
            item.log_record
            for item in log_exporter.get_finished_logs()
            if item.log_record.body == "http_request"
        )

        assert event["route"] == "/appointments/{appointment_id}"
        assert event["trace_id"] == f"{server_span.context.trace_id:032x}"
        assert event["span_id"] == f"{server_span.context.span_id:016x}"
        assert exported_request_log.trace_id == server_span.context.trace_id
        assert exported_request_log.span_id == server_span.context.span_id
        assert server_span.attributes["http.route"] == "/appointments/{appointment_id}"

        exported_span_text = " ".join(
            [
                *(span.name for span in spans),
                *(str(value) for span in spans for value in span.attributes.values()),
            ]
        )
        assert "private-appointment-id" not in exported_span_text
        assert "QuerySecret" not in exported_span_text
        assert "customer_name" not in exported_span_text
    finally:
        runtime.shutdown()


def test_health_endpoints_are_excluded_from_fastapi_tracing() -> None:
    span_exporter = InMemorySpanExporter()
    application = FastAPI()
    runtime = configure_telemetry(
        TelemetryConfig(enabled=True, export_logs=False, schedule_delay_millis=1),
        application=application,
        span_exporter=span_exporter,
        metric_reader=InMemoryMetricReader(),
    )

    @application.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready")
    async def readiness() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/example")
    async def business_request() -> dict[str, str]:
        return {"status": "ok"}

    try:
        with TestClient(application) as client:
            assert client.get("/health/live").status_code == 200
            assert client.get("/health/ready").status_code == 200
            assert client.get("/api/example").status_code == 200

        assert runtime.tracer_provider is not None
        assert runtime.tracer_provider.force_flush()
        server_spans = [
            span for span in span_exporter.get_finished_spans() if span.kind is SpanKind.SERVER
        ]

        assert [span.attributes["http.route"] for span in server_spans] == ["/api/example"]
    finally:
        runtime.shutdown()


def test_only_one_enabled_runtime_can_own_process_instrumentation() -> None:
    first = configure_telemetry(
        TelemetryConfig(enabled=True, export_logs=False),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )

    try:
        with pytest.raises(RuntimeError, match="one telemetry-enabled runtime"):
            configure_telemetry(
                TelemetryConfig(enabled=True, export_logs=False),
                span_exporter=InMemorySpanExporter(),
                metric_reader=InMemoryMetricReader(),
            )
    finally:
        first.shutdown()

    replacement = configure_telemetry(
        TelemetryConfig(enabled=True, export_logs=False),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )
    replacement.shutdown()


async def test_collector_outage_does_not_block_booking_path() -> None:
    exporter = BlockingFailingExporter()
    runtime = configure_telemetry(
        TelemetryConfig(
            enabled=True,
            export_logs=False,
            max_queue_size=8,
            max_export_batch_size=1,
            schedule_delay_millis=1,
            exporter_timeout_millis=20,
        ),
        span_exporter=exporter,
    )
    repository = BookingRepositoryStub()
    service = BookingService(repository, now_provider=lambda: NOW, telemetry=runtime)

    started = time.perf_counter()
    appointment = await service.create(
        "Cuong",
        datetime(2026, 10, 22, 10, 0, tzinfo=BOOKING_TIMEZONE),
    )
    elapsed = time.perf_counter() - started

    try:
        assert elapsed < 0.5
        assert appointment.status == AppointmentStatus.BOOKED.value
        assert repository.commits == 1
        assert exporter.export_started.wait(timeout=0.5)
    finally:
        exporter.release_export.set()
        runtime.shutdown()
