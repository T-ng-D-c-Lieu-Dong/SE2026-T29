"""Data persistence check across container recreate (E13).

Usage:
    python -m scripts.persistence_check seed --state-file /tmp/booking-e13.json
    docker compose up -d --force-recreate --no-deps backend
    python -m scripts.persistence_check verify --state-file /tmp/booking-e13.json

`seed` books the first free slot two days ahead and stores its id; `verify` reads the
appointment list back and requires the same booking to still be active.
Set the same BOOKING_PROBE_USER_ID (or --user-id) for both commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.smoke_test import SmokeTestRunner

PAGE_SIZE = 100


@dataclass
class PersistenceResult:
    success: bool
    message: str
    details: dict[str, Any]


class PersistenceCheck:
    def __init__(self, base_url: str = "http://localhost:8000", user_id: str | None = None) -> None:
        self._client = SmokeTestRunner(base_url=base_url, user_id=user_id)

    def _http_request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any] | list[Any] | str]:
        return self._client._http_request(method, path, body=body)

    def seed(self) -> PersistenceResult:
        target_date = (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%d")
        status, slots = self._http_request("GET", f"/api/slots?date={target_date}")
        if status != 200 or not isinstance(slots, list) or not slots:
            return PersistenceResult(
                False,
                f"No free slot found for {target_date} (HTTP {status})",
                {"status": status, "slots": slots},
            )

        starts_at = slots[0]["starts_at"]
        payload = {"customer_name": "[E13] Persistence Probe", "starts_at": starts_at}
        status, created = self._http_request("POST", "/api/appointments", body=payload)
        if status != 201 or not isinstance(created, dict) or "id" not in created:
            return PersistenceResult(
                False,
                f"POST /api/appointments failed with status {status}",
                {"status": status, "response": created},
            )

        return PersistenceResult(
            True,
            f"Seeded booking {created['id']} at {starts_at}",
            {"id": created["id"], "starts_at": starts_at},
        )

    def verify(self, appointment_id: str) -> PersistenceResult:
        offset = 0
        while True:
            status, page = self._http_request(
                "GET", f"/api/appointments?limit={PAGE_SIZE}&offset={offset}"
            )
            if status != 200 or not isinstance(page, dict):
                return PersistenceResult(
                    False,
                    f"GET /api/appointments failed with status {status}",
                    {"status": status, "response": page},
                )

            for item in page.get("items", []):
                if item.get("id") == appointment_id:
                    if item.get("status") != "booked":
                        return PersistenceResult(
                            False,
                            f"Booking {appointment_id} found but status is {item.get('status')}",
                            {"item": item},
                        )
                    return PersistenceResult(
                        True, f"Booking {appointment_id} survived recreate", {"item": item}
                    )

            offset += PAGE_SIZE
            if offset >= page.get("total", 0):
                return PersistenceResult(
                    False,
                    f"Booking {appointment_id} not found after recreate",
                    {"total": page.get("total")},
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Check bookings persist across recreate (E13)")
    parser.add_argument("action", choices=["seed", "verify"])
    parser.add_argument("--base-url", default="http://localhost:8000", help="Service base URL")
    parser.add_argument("--state-file", required=True, help="File storing the seeded booking")
    parser.add_argument(
        "--user-id", default=None, help="Probe identity (defaults to BOOKING_PROBE_USER_ID)"
    )
    args = parser.parse_args()

    check = PersistenceCheck(base_url=args.base_url, user_id=args.user_id)
    state_file = Path(args.state_file)

    if args.action == "seed":
        result = check.seed()
        if result.success:
            state_file.write_text(json.dumps(result.details), encoding="utf-8")
    else:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        result = check.verify(state["id"])

    print(f"[{'PASS' if result.success else 'FAIL'}] {args.action}: {result.message}")
    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
