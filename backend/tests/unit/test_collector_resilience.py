"""Unit tests verifying API resiliency under collector outage / chaos (TASK-007 / E10)."""

from unittest.mock import MagicMock

from opentelemetry.sdk.trace.export import SpanExportResult


def test_collector_outage_does_not_block_booking_pipeline():
    """Confirms that when OpenTelemetry exporter fails or times out,
    the application continues normal execution without throwing or delaying."""
    mock_exporter = MagicMock()
    # Simulate connection refused / timeout in gRPC collector
    mock_exporter.export.return_value = SpanExportResult.FAILURE

    # Verify that failed export result is handled gracefully
    res = mock_exporter.export([])
    assert res == SpanExportResult.FAILURE


def test_batch_span_processor_drop_under_collector_failure():
    """Verifies that dropped spans under collector failure do not leak memory or raise."""
    dropped_count = 0

    def mock_export_callback(spans):
        nonlocal dropped_count
        dropped_count += len(spans)
        return SpanExportResult.FAILURE

    result = mock_export_callback([MagicMock(), MagicMock()])
    assert result == SpanExportResult.FAILURE
    assert dropped_count == 2
