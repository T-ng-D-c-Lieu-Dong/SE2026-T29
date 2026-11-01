"""VT-119 load harness: N concurrent export requests against a running Booking API.

Usage:
  python scripts/vt119_export_load.py --seed        # seed 31 days x 48 slots (+cancelled rows)
  python scripts/vt119_export_load.py --users 150 --rounds 5 --target-p95 4.0

Measures wall-clock latency per request (client side) and prints p50/p95/p99, error counts and
whether p95 <= target. Exit code 1 if p95 exceeds the target or any non-200 is returned.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
START = date(2026, 11, 1)


async def seed(database_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE appointments"))
        rows = []
        for day in range(31):
            for slot in range(48):
                base = datetime.combine(START + timedelta(days=day), datetime.min.time(), tzinfo=TZ)
                starts = (base + timedelta(minutes=30 * slot)).astimezone(UTC)
                rows.append({"n": f"Customer {day}-{slot}", "s": starts, "st": "booked"})
                if slot % 3 == 0:
                    rows.append({"n": f"Cancelled {day}-{slot}", "s": starts, "st": "cancelled"})
        await conn.execute(
            text(
                "INSERT INTO appointments (id, customer_name, starts_at, status) "
                "VALUES (gen_random_uuid(), :n, :s, :st)"
            ),
            rows,
        )
    await engine.dispose()
    print(f"seeded {len(rows)} rows")


async def one(client: httpx.AsyncClient, url: str, headers: dict, params: dict):
    started = time.perf_counter()
    try:
        response = await client.get(url, headers=headers, params=params)
        return time.perf_counter() - started, response.status_code, len(response.content)
    except Exception as exc:  # noqa: BLE001 - record transport errors as failures
        return time.perf_counter() - started, type(exc).__name__, 0


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


async def run(args) -> int:
    url = f"{args.base_url}/api/exports/appointments"
    headers = {"X-API-Key": args.api_key}
    params = {"from": START.isoformat(), "to": (START + timedelta(days=30)).isoformat()}
    if args.include_cancelled:
        params["include_cancelled"] = "true"
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        await one(client, url, headers, params)  # warm-up, not measured
        results = []
        wall = time.perf_counter()
        for _ in range(args.rounds):
            batch = [one(client, url, headers, params) for _ in range(args.users)]
            results += await asyncio.gather(*batch)
        wall = time.perf_counter() - wall
    lat = [r[0] for r in results]
    codes: dict = {}
    for r in results:
        codes[r[1]] = codes.get(r[1], 0) + 1
    p95 = pct(lat, 0.95)
    print(f"requests={len(results)} users={args.users} rounds={args.rounds} wall={wall:.2f}s")
    print(f"status_counts={codes} body_bytes={results[-1][2]}")
    p50, p99 = statistics.median(lat), pct(lat, 0.99)
    print(f"p50={p50:.3f}s p95={p95:.3f}s p99={p99:.3f}s max={max(lat):.3f}s")
    ok = p95 <= args.target_p95 and set(codes) == {200}
    print(f"target_p95<={args.target_p95}s -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.getenv("EXPORT_LOAD_KEY", "k-staff"))
    parser.add_argument("--users", type=int, default=150)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--target-p95", type=float, default=4.0)
    parser.add_argument("--include-cancelled", action="store_true")
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "BOOKING_DATABASE_URL",
            "postgresql+asyncpg://booking:booking@localhost:5432/booking",
        ),
    )
    args = parser.parse_args()
    if args.seed:
        asyncio.run(seed(args.database_url))
        return 0
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
