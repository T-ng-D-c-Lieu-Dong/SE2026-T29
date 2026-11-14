"""120 concurrent in-process requests; fake repository, not a production load test."""

import asyncio
import math
import time

from app.api import appointments
from app.db import get_session
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class FakeService:
    def __init__(self, repository):
        pass

    async def list(self, limit, offset):
        await asyncio.sleep(0.01)  # simulated storage latency, no real database
        return [], 0


async def main():
    appointments.BookingService = FakeService
    app = FastAPI()
    app.include_router(appointments.router)
    app.dependency_overrides[get_session] = lambda: None
    durations = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def one():
            start = time.perf_counter()
            response = await client.get("/api/appointments?limit=7")
            durations.append(time.perf_counter() - start)
            assert response.status_code == 200
            assert response.json() == {"items": [], "total": 0, "limit": 7, "offset": 0}

        await asyncio.gather(*(one() for _ in range(120)))
    durations.sort()
    p95 = durations[math.ceil(0.95 * len(durations)) - 1]
    print(
        f"120 requests; successful business outcomes={len(durations)}; p95={p95:.6f}s; target=3.5s"
    )
    print("In-process ASGI, fake async repository 10ms; excludes network, database and deployment.")


if __name__ == "__main__":
    asyncio.run(main())
