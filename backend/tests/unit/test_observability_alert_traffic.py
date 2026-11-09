from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.observability_alert_traffic import build_booking_payload, run_alert_traffic


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_payload_uses_a_future_valid_slot_without_customer_data() -> None:
    payload = build_booking_payload(datetime(2026, 10, 25, 12, 0, tzinfo=UTC))

    assert payload == {
        "customer_name": "[E11] Bounded Alert Drill",
        "starts_at": "2026-10-27T10:00:00+07:00",
    }


def test_alert_traffic_holds_the_requested_rate_and_counts_statuses() -> None:
    clock = FakeClock()

    summary = run_alert_traffic(
        request_sender=lambda: 500,
        requests_per_second=2,
        duration_seconds=2,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    assert summary.attempted == 4
    assert summary.status_counts == {500: 4}
    assert summary.transport_errors == 0
    assert summary.elapsed_seconds == pytest.approx(2)
    assert summary.success


def test_alert_traffic_fails_when_responses_do_not_match_expected_status() -> None:
    clock = FakeClock()
    statuses = iter([500, 201])

    summary = run_alert_traffic(
        request_sender=lambda: next(statuses),
        requests_per_second=1,
        duration_seconds=2,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    assert summary.status_counts == {201: 1, 500: 1}
    assert not summary.success
