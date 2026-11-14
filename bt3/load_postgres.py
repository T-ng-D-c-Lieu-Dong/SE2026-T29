"""Local HTTP + PostgreSQL test, only against the dedicated booking_test DB."""

import asyncio
import math
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from app.db import Base
from app.models import Appointment
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import create_async_engine

URL = "postgresql+asyncpg://booking:booking@localhost:55432/booking_test"
IDS = [uuid4(), uuid4()]


async def main():
    engine = create_async_engine(URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        count = await conn.scalar(select(func.count()).select_from(Appointment))
        if count != 0:
            raise RuntimeError("Test database is not empty; refusing to seed")
        await conn.execute(
            Appointment.__table__.insert(),
            [
                {
                    "id": IDS[0],
                    "customer_name": "Load-A",
                    "starts_at": datetime(2090, 1, 1, 10, tzinfo=UTC),
                },
                {
                    "id": IDS[1],
                    "customer_name": "Load-B",
                    "starts_at": datetime(2090, 1, 2, 10, tzinfo=UTC),
                },
            ],
        )
    env = os.environ.copy()
    env["BOOKING_DATABASE_URL"] = URL
    env["BOOKING_DEFAULT_PAGE_SIZE"] = "1"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18976",
        "--log-level",
        "warning",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:18976",
            timeout=15,
            limits=httpx.Limits(max_connections=120, max_keepalive_connections=120),
        ) as client:
            for _ in range(100):
                if process.returncode is not None:
                    raise RuntimeError("Server process exited before it became ready")
                try:
                    if (await client.get("/health/live")).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("Server did not become ready")
            elapsed = []
            outcomes = []

            async def request():
                start = time.perf_counter()
                try:
                    response = await client.get("/api/appointments")
                    result = response.json()
                    ok = (
                        response.status_code == 200
                        and result["limit"] == 1
                        and result["total"] == 2
                        and len(result["items"]) == 1
                        and result["items"][0]["customer_name"] == "Load-A"
                    )
                    outcomes.append(ok)
                except Exception:
                    outcomes.append(False)
                elapsed.append(time.perf_counter() - start)

            start = time.perf_counter()
            await asyncio.gather(*(request() for _ in range(120)))
            wall = time.perf_counter() - start
            elapsed.sort()
            p95 = elapsed[math.ceil(0.95 * 120) - 1]
            print(
                f"concurrent=120; correct={sum(outcomes)}/120; errors={120 - sum(outcomes)}; "
                f"p95_nearest_rank={p95:.6f}s; elapsed={wall:.6f}s; target=3.5s"
            )
            print(
                "localhost HTTP; uvicorn 1 worker; PostgreSQL 18 test container; "
                "2 seeded rows; no warmup; single burst"
            )
            if not all(outcomes):
                raise RuntimeError("Some business outcomes failed")
    finally:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=10)
        async with engine.begin() as conn:
            await conn.execute(delete(Appointment).where(Appointment.id.in_(IDS)))
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
