"""Generate bounded booking failures for the TASK-006 HighErrorRate drill."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

MINIMUM_REQUESTS_PER_SECOND = 100 / 60
MINIMUM_DURATION_SECONDS = 195


@dataclass(frozen=True, slots=True)
class TrafficSummary:
    attempted: int
    status_counts: dict[int, int]
    transport_errors: int
    elapsed_seconds: float
    expected_status: int

    @property
    def success(self) -> bool:
        return (
            self.attempted > 0
            and self.transport_errors == 0
            and self.status_counts == {self.expected_status: self.attempted}
        )


def build_booking_payload(now: datetime | None = None) -> dict[str, str]:
    current = now or datetime.now(UTC)
    target_date = (current + timedelta(days=2)).date().isoformat()
    return {
        "customer_name": "[E11] Bounded Alert Drill",
        "starts_at": f"{target_date}T10:00:00+07:00",
    }


def send_booking_request(
    base_url: str,
    payload: dict[str, str],
    *,
    timeout_seconds: float = 5.0,
) -> int:
    request = urllib.request.Request(  # noqa: S310 - operator-supplied drill endpoint
        f"{base_url.rstrip('/')}/api/appointments",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def run_alert_traffic(
    *,
    request_sender: Callable[[], int],
    requests_per_second: float,
    duration_seconds: float,
    expected_status: int = 500,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> TrafficSummary:
    if requests_per_second <= 0:
        raise ValueError("requests_per_second must be greater than zero")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")

    interval = 1 / requests_per_second
    started = monotonic()
    deadline = started + duration_seconds
    next_request_at = started
    attempted = 0
    transport_errors = 0
    statuses: Counter[int] = Counter()

    while monotonic() < deadline:
        wait_seconds = next_request_at - monotonic()
        if wait_seconds > 0:
            sleeper(wait_seconds)
        if monotonic() >= deadline:
            break

        attempted += 1
        try:
            statuses[request_sender()] += 1
        except (OSError, TimeoutError, urllib.error.URLError):
            transport_errors += 1

        next_request_at += interval
        if next_request_at < monotonic():
            next_request_at = monotonic()

    return TrafficSummary(
        attempted=attempted,
        status_counts=dict(sorted(statuses.items())),
        transport_errors=transport_errors,
        elapsed_seconds=monotonic() - started,
        expected_status=expected_status,
    )


def _summary_document(summary: TrafficSummary, started_at: datetime) -> dict[str, Any]:
    return {
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
        "attempted": summary.attempted,
        "status_counts": {str(key): value for key, value in summary.status_counts.items()},
        "transport_errors": summary.transport_errors,
        "elapsed_seconds": round(summary.elapsed_seconds, 3),
        "expected_status": summary.expected_status,
        "success": summary.success,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate bounded POST failures for the TASK-006 HighErrorRate drill"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--rate", type=float, default=2.0, help="Requests per second")
    parser.add_argument("--duration", type=float, default=210.0, help="Duration in seconds")
    parser.add_argument("--expected-status", type=int, default=500)
    args = parser.parse_args()

    if args.rate < MINIMUM_REQUESTS_PER_SECOND:
        parser.error("--rate must produce at least 100 requests per minute")
    if args.duration < MINIMUM_DURATION_SECONDS:
        parser.error("--duration must cover the one-minute window and two-minute alert delay")

    payload = build_booking_payload()
    started_at = datetime.now(UTC)
    summary = run_alert_traffic(
        request_sender=lambda: send_booking_request(args.base_url, payload),
        requests_per_second=args.rate,
        duration_seconds=args.duration,
        expected_status=args.expected_status,
    )
    print(json.dumps(_summary_document(summary, started_at), separators=(",", ":")))
    if not summary.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
