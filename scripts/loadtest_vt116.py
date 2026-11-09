"""Load test harness for VT-116: 40 concurrent tasks, target p95 <= 1.5s.
Measures latency of appointment creation, soft-delete, and restore against live PostgreSQL.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add repository root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db import Base, get_session
from app.main import create_app

BOOKING_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
CONCURRENCY = 40
TOTAL_REQUESTS = 200
TARGET_P95_SECONDS = 1.5


def calculate_percentile(data: list[float], percentile: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


async def run_load_test() -> dict[str, Any]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        print("ERROR: TEST_DATABASE_URL is required.")
        sys.exit(1)

    db_name = make_url(database_url).database or ""
    if not db_name.endswith("_test"):
        print(f"ERROR: Refusing to run against non-test database: {db_name}")
        sys.exit(1)

    print(f"[*] Initializing test database engine: {db_name}")
    engine = create_async_engine(database_url, pool_size=50, max_overflow=20)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE appointments"))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    sem = asyncio.Semaphore(CONCURRENCY)
    latencies: list[float] = []
    success_count = 0
    error_count = 0

    base_time = (datetime.now(BOOKING_TIMEZONE) + timedelta(days=30)).replace(
        minute=0, second=0, microsecond=0
    )

    async def task_worker(worker_id: int, client: AsyncClient) -> None:
        nonlocal success_count, error_count
        async with sem:
            caller_id = f"load_user_{worker_id}"
            # Ensure each task has a completely independent 30-min slot in the future
            slot = (base_time + timedelta(minutes=30 * worker_id)).replace(
                second=0, microsecond=0
            )

            # Measure full lifecycle: Create -> Soft-Delete -> Restore
            t0 = time.perf_counter()
            try:
                # 1. Create booking
                create_resp = await client.post(
                    "/api/appointments",
                    json={"customer_name": f"User_{worker_id}", "starts_at": slot.isoformat()},
                    headers={"X-User-Id": caller_id},
                )
                if create_resp.status_code != 201:
                    error_count += 1
                    return
                apt_id = create_resp.json()["id"]

                # 2. Soft-delete booking
                del_resp = await client.patch(
                    f"/api/appointments/{apt_id}/soft-delete",
                    headers={"X-User-Id": caller_id},
                )
                if del_resp.status_code != 200:
                    error_count += 1
                    return

                # 3. Restore booking
                res_resp = await client.patch(
                    f"/api/appointments/{apt_id}/restore",
                    headers={"X-User-Id": caller_id},
                )
                if res_resp.status_code != 200:
                    error_count += 1
                    return

                duration = time.perf_counter() - t0
                latencies.append(duration)
                success_count += 1
            except Exception as e:
                error_count += 1

    print(f"[*] Starting Load Test: {TOTAL_REQUESTS} lifecycle tasks with {CONCURRENCY} concurrent workers...")
    test_start = time.perf_counter()

    async with AsyncClient(transport=transport, base_url="http://loadtest", timeout=30.0) as client:
        # Warmup with 5 requests
        for w in range(5):
            await task_worker(9000 + w, client)
        latencies.clear()
        success_count = 0
        error_count = 0

        # Official measurement run
        tasks = [task_worker(i, client) for i in range(TOTAL_REQUESTS)]
        await asyncio.gather(*tasks)

    total_duration = time.perf_counter() - test_start

    p50 = calculate_percentile(latencies, 50.0)
    p95 = calculate_percentile(latencies, 95.0)
    p99 = calculate_percentile(latencies, 99.0)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    throughput = len(latencies) / total_duration if total_duration > 0 else 0.0

    result = {
        "variant": "VT-116",
        "timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
        "database": "PostgreSQL 18-alpine (Docker)",
        "concurrency_inflight": CONCURRENCY,
        "total_lifecycle_tasks": TOTAL_REQUESTS,
        "completed_tasks": len(latencies),
        "success_rate_percent": round((success_count / TOTAL_REQUESTS) * 100, 2),
        "error_count": error_count,
        "total_duration_seconds": round(total_duration, 4),
        "throughput_tasks_per_sec": round(throughput, 2),
        "latency_stats_seconds": {
            "avg": round(avg_latency, 4),
            "p50": round(p50, 4),
            "p95": round(p95, 4),
            "p99": round(p99, 4),
            "min": round(min(latencies), 4) if latencies else 0.0,
            "max": round(max(latencies), 4) if latencies else 0.0,
        },
        "target_p95_seconds": TARGET_P95_SECONDS,
        "passed_performance_goal": p95 <= TARGET_P95_SECONDS,
    }

    print("\n" + "=" * 60)
    print("           VT-116 LOAD TEST EXPERIMENT RESULTS")
    print("=" * 60)
    print(f"Concurrency (In-flight tasks) : {CONCURRENCY}")
    print(f"Total Completed Tasks         : {len(latencies)} / {TOTAL_REQUESTS}")
    print(f"Success Rate                  : {result['success_rate_percent']}%")
    print(f"Total Execution Time          : {result['total_duration_seconds']} s")
    print(f"Throughput                    : {result['throughput_tasks_per_sec']} tasks/sec")
    print(f"Average Latency               : {result['latency_stats_seconds']['avg'] * 1000:.2f} ms")
    print(f"p50 Latency                   : {result['latency_stats_seconds']['p50'] * 1000:.2f} ms")
    print(f"p95 Latency                   : {result['latency_stats_seconds']['p95'] * 1000:.2f} ms")
    print(f"p99 Latency                   : {result['latency_stats_seconds']['p99'] * 1000:.2f} ms")
    print(f"Target p95                    : <= {TARGET_P95_SECONDS * 1000:.1f} ms")
    print(f"Performance Goal Status       : {'PASSED (MEETS P95 <= 1.5s)' if result['passed_performance_goal'] else 'FAILED'}")
    print("=" * 60)

    # Cleanup
    await engine.dispose()
    return result


if __name__ == "__main__":
    res = asyncio.run(run_load_test())
    output_path = os.path.join(os.path.dirname(__file__), "..", "docs", "bt3-vt116", "evidence", "04-performance.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Results saved to {output_path}")
