"""VT-118 load harness: N concurrent workers create bookings and the p95 latency is checked.

Each scenario:
1. truncates ``appointments`` in the dedicated load database (name must end in ``_test``);
2. starts ``--concurrency`` workers behind one barrier so they really run at the same time;
3. each worker sends ``--requests-per-worker`` ``POST /api/appointments`` requests on unique slots;
4. reports p50/p95/p99/max, status counts, ``notification_status`` counts, peak in-flight requests,
   and checks that the number of booked rows equals the number of 201 responses.

p95 uses the nearest-rank method over every request of the scenario.

Example::

    python loadtest/vt118/load_notifications.py --scenario hang --payload valid \
        --db-url postgresql://booking:booking@127.0.0.1:55432/booking_load_test \
        --output docs/vt118/evidence/load/after-hang.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg
import httpx

BOOKING_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
PAYLOAD_NAMES = {
    "valid": "Load Customer",
    "valid-100": "N" * 100,
    "oversized-1mb": "X" * 1_000_000,
}


def nearest_rank(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return float("nan")
    rank = max(1, math.ceil(percentile / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def slot_for(index: int, first_day_offset: int) -> datetime:
    day = datetime.now(BOOKING_TIMEZONE).date() + timedelta(days=first_day_offset)
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=BOOKING_TIMEZONE)
    return midnight + timedelta(minutes=30 * index)


async def reset_database(db_url: str) -> None:
    if not db_url.rsplit("/", 1)[-1].endswith("_test"):
        raise SystemExit("Refusing to truncate a database whose name does not end in _test")
    connection = await asyncpg.connect(db_url)
    try:
        await connection.execute("TRUNCATE TABLE appointments")
    finally:
        await connection.close()


async def count_booked(db_url: str) -> int:
    connection = await asyncpg.connect(db_url)
    try:
        return await connection.fetchval(
            "SELECT count(*) FROM appointments WHERE status = 'booked'"
        )
    finally:
        await connection.close()


async def run_scenario(args: argparse.Namespace) -> dict[str, object]:
    await reset_database(args.db_url)
    name = PAYLOAD_NAMES[args.payload]
    latencies: list[float] = []
    statuses: Counter[int] = Counter()
    notification_statuses: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    in_flight = 0
    peak_in_flight = 0
    start_gate = asyncio.Event()
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=0)

    async with httpx.AsyncClient(
        base_url=args.base_url, limits=limits, timeout=args.timeout
    ) as client:

        async def worker(worker_index: int) -> None:
            nonlocal in_flight, peak_in_flight
            await start_gate.wait()
            for request_index in range(args.requests_per_worker):
                slot_index = worker_index * args.requests_per_worker + request_index
                body = {
                    "customer_name": name,
                    "starts_at": slot_for(slot_index, args.first_day_offset).isoformat(),
                }
                in_flight += 1
                peak_in_flight = max(peak_in_flight, in_flight)
                started = time.perf_counter()
                try:
                    response = await client.post("/api/appointments", json=body)
                except httpx.HTTPError as exc:
                    errors[type(exc).__name__] += 1
                    latencies.append(time.perf_counter() - started)
                    continue
                finally:
                    in_flight -= 1
                latencies.append(time.perf_counter() - started)
                statuses[response.status_code] += 1
                if response.status_code == 201:
                    notification_statuses[
                        response.json().get("notification_status", "<missing>")
                    ] += 1

        workers = [asyncio.create_task(worker(index)) for index in range(args.concurrency)]
        await asyncio.sleep(0.2)
        wall_started = time.perf_counter()
        start_gate.set()
        await asyncio.gather(*workers)
        wall_seconds = time.perf_counter() - wall_started

    ordered = sorted(latencies)
    booked_rows = await count_booked(args.db_url)
    p95 = nearest_rank(ordered, 95)
    server_errors = sum(count for status, count in statuses.items() if status >= 500)
    created = statuses.get(201, 0)
    result: dict[str, object] = {
        "scenario": args.scenario,
        "payload": args.payload,
        "payload_customer_name_chars": len(name),
        "concurrency": args.concurrency,
        "requests_per_worker": args.requests_per_worker,
        "total_requests": len(latencies),
        "peak_in_flight": peak_in_flight,
        "wall_seconds": round(wall_seconds, 3),
        "throughput_rps": round(len(latencies) / wall_seconds, 1) if wall_seconds else None,
        "latency_seconds": {
            "p50": round(nearest_rank(ordered, 50), 4),
            "p95": round(p95, 4),
            "p99": round(nearest_rank(ordered, 99), 4),
            "max": round(ordered[-1], 4) if ordered else None,
        },
        "status_counts": {str(key): value for key, value in sorted(statuses.items())},
        "client_errors": dict(errors),
        "notification_status_counts": dict(notification_statuses),
        "booked_rows_in_db": booked_rows,
        "rows_match_201": booked_rows == created,
        "target_p95_seconds": args.target_p95,
        "p95_within_target": p95 <= args.target_p95,
        "no_5xx": server_errors == 0 and not errors,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, help="label stored in the report")
    parser.add_argument("--payload", choices=sorted(PAYLOAD_NAMES), default="valid")
    parser.add_argument("--base-url", default="http://127.0.0.1:8018")
    parser.add_argument("--db-url", required=True, help="plain postgresql:// URL of *_test DB")
    parser.add_argument("--concurrency", type=int, default=60)
    parser.add_argument("--requests-per-worker", type=int, default=10)
    parser.add_argument("--first-day-offset", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--target-p95", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = asyncio.run(run_scenario(args))
    text = json.dumps(result, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
