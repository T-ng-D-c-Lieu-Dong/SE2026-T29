"""Error budget and burn rate calculator (TASK-007 Hardening).

Implements multi-window multi-burn-rate alerting logic per Google SRE Workbook:
- SLO target: 99.0% availability for Booking API (< 1% error rate).
- Total Error Budget: 1.0% of total requests over a rolling 30-day window.
- Burn rate thresholds:
    - 14.4x (2% budget consumed in 1 hour) -> Critical alert (Page).
    - 6.0x (5% budget consumed in 6 hours) -> Warning alert (Ticket).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass


@dataclass
class BurnRateResult:
    slo_target: float
    total_requests: int
    error_requests: int
    observed_error_rate: float
    burn_rate: float
    consumed_budget_percent: float
    status: str

    @property
    def is_violating(self) -> bool:
        return self.status in ("CRITICAL", "WARNING")


class ErrorBudgetCalculator:
    def __init__(self, slo_target: float = 0.99) -> None:
        if not (0.0 < slo_target < 1.0):
            raise ValueError(f"SLO target must be between 0 and 1, got {slo_target}")
        self.slo_target = slo_target
        self.allowed_error_fraction = 1.0 - slo_target

    def calculate(
        self,
        total_requests: int,
        error_requests: int,
        window_hours: float = 1.0,
    ) -> BurnRateResult:
        if total_requests < 0 or error_requests < 0:
            raise ValueError("Requests cannot be negative")
        if error_requests > total_requests:
            raise ValueError("Error requests cannot exceed total requests")

        if total_requests == 0:
            return BurnRateResult(
                slo_target=self.slo_target,
                total_requests=0,
                error_requests=0,
                observed_error_rate=0.0,
                burn_rate=0.0,
                consumed_budget_percent=0.0,
                status="OK",
            )

        error_rate = error_requests / total_requests
        # Burn rate is the ratio of observed error rate to the allowed error rate
        burn_rate = error_rate / self.allowed_error_fraction

        # In a 30-day (720 hours) period, fraction of period represented by window:
        window_fraction = window_hours / 720.0
        consumed_budget = (burn_rate * window_fraction) * 100.0

        if burn_rate >= 14.4:
            status = "CRITICAL"
        elif burn_rate >= 6.0:
            status = "WARNING"
        else:
            status = "OK"

        return BurnRateResult(
            slo_target=self.slo_target,
            total_requests=total_requests,
            error_requests=error_requests,
            observed_error_rate=error_rate,
            burn_rate=round(burn_rate, 2),
            consumed_budget_percent=round(consumed_budget, 2),
            status=status,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate Error Budget and Burn Rate")
    parser.add_argument("--total", type=int, required=True, help="Total requests in window")
    parser.add_argument("--errors", type=int, required=True, help="5xx/failed requests in window")
    parser.add_argument("--window-hours", type=float, default=1.0, help="Window duration in hours")
    parser.add_argument("--slo", type=float, default=0.99, help="SLO target (e.g. 0.99 for 99%)")

    args = parser.parse_args()
    calc = ErrorBudgetCalculator(slo_target=args.slo)
    res = calc.calculate(args.total, args.errors, window_hours=args.window_hours)

    print("=" * 60)
    print(f"SLO Target: {res.slo_target * 100:.1f}%")
    print(
        f"Window: {args.window_hours}h | Total: {res.total_requests} | Errors: {res.error_requests}"
    )
    print(f"Observed Error Rate: {res.observed_error_rate * 100:.2f}%")
    print(f"Burn Rate: {res.burn_rate}x (Budget consumed: {res.consumed_budget_percent}%)")
    print(f"Status: [{res.status}]")
    print("=" * 60)

    if res.is_violating:
        sys.exit(1)


if __name__ == "__main__":
    main()
