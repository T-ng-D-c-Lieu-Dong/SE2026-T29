"""Load test harness for VT-116: 40 concurrent tasks, target p95 <= 1.5s.

Measures latency of appointment creation, soft-delete, and restore against live PostgreSQL.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import subprocess
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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


def performance_goal_met(latencies: list[float], error_count: int, total_tasks: int) -> bool:
    return (
        len(latencies) == total_tasks
        and total_tasks > 0
        and error_count == 0
        and calculate_percentile(latencies, 95) <= TARGET_P95_SECONDS
    )


async def run_load_test() -> dict[str, object]:
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
        _ = await conn.execute(text("TRUNCATE TABLE appointments"))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    sem = asyncio.Semaphore(CONCURRENCY)
    latencies: list[float] = []
    samples: list[dict[str, object]] = []
    active_tasks = peak_tasks = active_requests = peak_requests = request_count = 0

    async def request(client: AsyncClient, method: str, url: str, **kwargs):
        nonlocal active_requests, peak_requests, request_count
        active_requests += 1
        peak_requests = max(peak_requests, active_requests)
        request_count += 1
        try:
            return await client.request(method, url, **kwargs)
        finally:
            active_requests -= 1

    success_count = 0
    error_count = 0

    base_time = (datetime.now(BOOKING_TIMEZONE) + timedelta(days=30)).replace(
        minute=0, second=0, microsecond=0
    )

    async def task_worker(worker_id: int, client: AsyncClient) -> None:
        nonlocal success_count, error_count, active_tasks, peak_tasks
        async with sem:
            active_tasks += 1
            peak_tasks = max(peak_tasks, active_tasks)
            caller_id = f"load_user_{worker_id}"
            slot = (base_time + timedelta(minutes=30 * worker_id)).replace(second=0, microsecond=0)

            t0 = time.perf_counter()
            try:
                # 1. Create booking
                create_resp = await request(
                    client,
                    "POST",
                    "/api/appointments",
                    json={"customer_name": f"User_{worker_id}", "starts_at": slot.isoformat()},
                    headers={"X-User-Id": caller_id},
                )
                if create_resp.status_code != 201:
                    raise RuntimeError(f"HTTP {create_resp.status_code}: create failed")
                resp_json = cast(dict[str, object], create_resp.json())
                apt_id = str(resp_json.get("id", ""))

                # 2. Soft-delete booking
                del_resp = await request(
                    client,
                    "PATCH",
                    f"/api/appointments/{apt_id}/soft-delete",
                    headers={"X-User-Id": caller_id},
                )
                if del_resp.status_code != 200:
                    raise RuntimeError(f"HTTP {del_resp.status_code}: soft-delete failed")

                # 3. Restore booking
                res_resp = await request(
                    client,
                    "PATCH",
                    f"/api/appointments/{apt_id}/restore",
                    headers={"X-User-Id": caller_id},
                )
                if res_resp.status_code != 200:
                    raise RuntimeError(f"HTTP {res_resp.status_code}: restore failed")

                duration = time.perf_counter() - t0
                latencies.append(duration)
                success_count += 1
                samples.append(
                    {"worker_id": worker_id, "latency_seconds": duration, "success": True}
                )
            except Exception as exc:
                error_count += 1
                samples.append({"worker_id": worker_id, "success": False, "error": str(exc)})
            finally:
                active_tasks -= 1

    print(
        f"[*] Starting Load Test: {TOTAL_REQUESTS} tasks with {CONCURRENCY} concurrent workers..."
    )

    async with AsyncClient(transport=transport, base_url="http://loadtest", timeout=30.0) as client:
        # Warmup with 5 requests
        for w in range(5):
            await task_worker(9000 + w, client)
        warmup_errors = error_count
        latencies.clear()
        samples.clear()
        active_tasks = peak_tasks = active_requests = peak_requests = request_count = 0
        success_count = 0
        error_count = 0

        # Official measurement run: warmup excluded from all counters and duration.
        test_start = time.perf_counter()
        tasks = [task_worker(i, client) for i in range(TOTAL_REQUESTS)]
        _ = await asyncio.gather(*tasks)
        total_duration = time.perf_counter() - test_start

    p50 = calculate_percentile(latencies, 50.0)
    p95 = calculate_percentile(latencies, 95.0)
    p99 = calculate_percentile(latencies, 99.0)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    throughput = len(latencies) / total_duration if total_duration > 0 else 0.0

    goal_met = performance_goal_met(latencies, error_count, TOTAL_REQUESTS) and warmup_errors == 0
    status_str = "PASSED (MEETS P95 <= 1.5s)" if goal_met else "FAILED"
    success_rate = round((success_count / TOTAL_REQUESTS) * 100, 2)

    latency_stats: dict[str, float] = {
        "avg": avg_latency,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "min": min(latencies) if latencies else 0.0,
        "max": max(latencies) if latencies else 0.0,
    }

    result: dict[str, object] = {
        "run_id": datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8],
        "tested_commit": (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "transport": "httpx ASGITransport in-process; real PostgreSQL; no network HTTP server",
        "variant": "VT-116",
        "timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
        "database": "PostgreSQL 18-alpine (Docker)",
        "concurrency_cap": CONCURRENCY,
        "peak_lifecycle_inflight": peak_tasks,
        "peak_http_inflight": peak_requests,
        "measured_request_count": request_count,
        "warmup_lifecycles": 5,
        "warmup_errors": warmup_errors,
        "error_rate_percent": round(error_count / TOTAL_REQUESTS * 100, 4),
        "total_lifecycle_tasks": TOTAL_REQUESTS,
        "completed_tasks": len(latencies),
        "success_rate_percent": success_rate,
        "error_count": error_count,
        "total_duration_seconds": round(total_duration, 4),
        "throughput_tasks_per_sec": round(throughput, 2),
        "latency_stats_seconds": latency_stats,
        "target_p95_seconds": TARGET_P95_SECONDS,
        "passed_performance_goal": goal_met,
        "samples": samples,
    }

    print("\n" + "=" * 60)
    print("           VT-116 LOAD TEST EXPERIMENT RESULTS")
    print("=" * 60)
    print(f"Run ID                        : {result['run_id']}")
    print(f"Tested commit                 : {result['tested_commit']}")
    print(f"Concurrency cap               : {CONCURRENCY}")
    print(f"Peak lifecycle / HTTP in-flight: {peak_tasks} / {peak_requests}")
    print(f"Measured HTTP requests        : {request_count}")
    print("Transport                     : in-process ASGI; real PostgreSQL")
    print(f"Total Completed Tasks         : {len(latencies)} / {TOTAL_REQUESTS}")
    print(f"Success Rate                  : {success_rate}%")
    print(f"Total Execution Time          : {result['total_duration_seconds']} s")
    print(f"Throughput                    : {result['throughput_tasks_per_sec']} tasks/sec")
    print(f"Average Latency               : {avg_latency * 1000:.2f} ms")
    print(f"p50 Latency                   : {p50 * 1000:.2f} ms")
    print(f"p95 Latency                   : {p95 * 1000:.2f} ms")
    print(f"p99 Latency                   : {p99 * 1000:.2f} ms")
    print(
        f"Min / Max latency             : {min(latencies, default=0) * 1000:.2f} / "
        f"{max(latencies, default=0) * 1000:.2f} ms"
    )
    print(f"Errors / error rate            : {error_count} / {result['error_rate_percent']}%")
    print(f"Warmup errors                 : {warmup_errors}")
    print(f"Target p95                    : <= {TARGET_P95_SECONDS * 1000:.1f} ms")
    print(f"Performance Goal Status       : {status_str}")
    print("=" * 60)

    # Cleanup
    await engine.dispose()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs/bt3-vt116/evidence/final",
    )
    args = parser.parse_args()
    captured = io.StringIO()
    with redirect_stdout(captured):
        res = asyncio.run(run_load_test())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / ("performance-" + str(res["run_id"]))
    stem.with_suffix(".json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    stem.with_suffix(".log").write_text(captured.getvalue())
    print(captured.getvalue())
    print(f"Paired evidence: {stem}.json / .log")
    sys.exit(0 if res["passed_performance_goal"] else 1)
