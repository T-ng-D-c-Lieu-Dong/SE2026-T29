"""Booking integrity checker before and after rollback (E12 / E14 verification).

Proves that pre-existing booking appointments are never lost, corrupted, or altered
across rollback and deployment drills.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class BookingRecord:
    id: str
    customer_name: str
    starts_at: str
    status: str

    def matches(self, other: BookingRecord) -> bool:
        return (
            self.id == other.id
            and self.customer_name == other.customer_name
            and self.starts_at == other.starts_at
            and self.status == other.status
        )


@dataclass
class IntegritySnapshot:
    captured_at: str
    base_url: str
    count: int
    bookings: dict[str, dict[str, str]] = field(default_factory=dict)

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> IntegritySnapshot:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Snapshot file not found: {path}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(**data)


@dataclass
class IntegrityReport:
    verified_at: str
    baseline_count: int
    current_count: int
    intact_count: int
    missing_ids: list[str] = field(default_factory=list)
    corrupted_ids: dict[str, dict[str, Any]] = field(default_factory=dict)
    new_ids: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.missing_ids) == 0 and len(self.corrupted_ids) == 0


def fetch_bookings(
    base_url: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> list[BookingRecord]:
    """Fetch all appointments from /api/appointments with resilient retry for temporary connection resets."""
    url = f"{base_url.rstrip('/')}/api/appointments?limit=1000"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "booking-integrity-check/1.0"},
    )
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} querying {url}")
                data = json.loads(resp.read().decode("utf-8"))
                break
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise RuntimeError(
                    f"Failed to fetch appointments from {url} after {max_retries} attempts: {exc}"
                ) from exc
    else:
        if last_err:
            raise last_err
        raise RuntimeError(f"Failed querying {url}")

    items = data.get("items", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Invalid appointments response format")

    records: list[BookingRecord] = []
    for item in items:
        if isinstance(item, dict) and "id" in item:
            records.append(
                BookingRecord(
                    id=str(item["id"]),
                    customer_name=str(item.get("customer_name", "")),
                    starts_at=str(item.get("starts_at", "")),
                    status=str(item.get("status", "")),
                )
            )
    return records


def create_snapshot(base_url: str, now: datetime | None = None) -> IntegritySnapshot:
    records = fetch_bookings(base_url)
    ts = (now or datetime.now(UTC)).isoformat()
    mapping = {r.id: asdict(r) for r in records}
    return IntegritySnapshot(
        captured_at=ts,
        base_url=base_url,
        count=len(mapping),
        bookings=mapping,
    )


def verify_integrity(
    baseline: IntegritySnapshot,
    current_records: list[BookingRecord],
    now: datetime | None = None,
) -> IntegrityReport:
    ts = (now or datetime.now(UTC)).isoformat()
    current_map = {r.id: r for r in current_records}

    intact = 0
    missing: list[str] = []
    corrupted: dict[str, dict[str, Any]] = {}

    for b_id, b_dict in baseline.bookings.items():
        base_record = BookingRecord(**b_dict)
        if b_id not in current_map:
            missing.append(b_id)
        else:
            curr = current_map[b_id]
            if base_record.matches(curr):
                intact += 1
            else:
                corrupted[b_id] = {
                    "expected": asdict(base_record),
                    "actual": asdict(curr),
                }

    new_ids = [r.id for r in current_records if r.id not in baseline.bookings]

    return IntegrityReport(
        verified_at=ts,
        baseline_count=baseline.count,
        current_count=len(current_records),
        intact_count=intact,
        missing_ids=missing,
        corrupted_ids=corrupted,
        new_ids=new_ids,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Booking integrity snapshot and verification.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snap_p = subparsers.add_parser("snapshot", help="Capture current bookings into snapshot file")
    snap_p.add_argument("--base-url", default="http://localhost:8000", help="Base API URL")
    snap_p.add_argument("--output", required=True, help="Path to save snapshot JSON")

    ver_p = subparsers.add_parser("verify", help="Verify current bookings against snapshot")
    ver_p.add_argument("--base-url", default="http://localhost:8000", help="Base API URL")
    ver_p.add_argument("--baseline", required=True, help="Path to baseline snapshot JSON")
    ver_p.add_argument("--report", help="Optional path to output verification report JSON")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "snapshot":
        try:
            snapshot = create_snapshot(args.base_url)
            snapshot.save(args.output)
            print(f"[OK] Captured {snapshot.count} bookings to {args.output}")
        except Exception as e:
            print(f"[ERROR] Failed to take snapshot: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "verify":
        try:
            baseline = IntegritySnapshot.load(args.baseline)
            current_records = fetch_bookings(args.base_url)
            report = verify_integrity(baseline, current_records)

            if args.report:
                Path(args.report).write_text(
                    json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8"
                )

            print(f"Baseline bookings : {report.baseline_count}")
            print(f"Current bookings  : {report.current_count}")
            print(f"Intact bookings   : {report.intact_count} / {report.baseline_count}")
            print(f"Missing bookings  : {len(report.missing_ids)}")
            print(f"Corrupted bookings: {len(report.corrupted_ids)}")
            print(f"New bookings      : {len(report.new_ids)}")

            if report.is_valid:
                print("\n[PASS] 100% pre-existing bookings preserved. Zero data loss.")
            else:
                print(
                    f"\n[FAIL] Integrity violation! Missing: {report.missing_ids}, "
                    f"Corrupted: {report.corrupted_ids}",
                    file=sys.stderr,
                )
                sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Verification failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
