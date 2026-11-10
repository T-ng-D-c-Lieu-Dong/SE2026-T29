"""Experiment (plan review R1/R6): does ASGITransport wait for BackgroundTasks or run lifespan?"""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from httpx import ASGITransport, AsyncClient

events: list[str] = []


@asynccontextmanager
async def lifespan(application: FastAPI):
    events.append("lifespan-startup")
    yield
    events.append("lifespan-shutdown")


app = FastAPI(lifespan=lifespan)


async def slow_task() -> None:
    await asyncio.sleep(1.0)
    events.append("bg-done")


@app.post("/x")
async def endpoint(background: BackgroundTasks) -> dict[str, bool]:
    background.add_task(slow_task)
    return {"ok": True}


async def main() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        started = time.perf_counter()
        response = await client.post("/x")
        elapsed = time.perf_counter() - started
    print(f"status={response.status_code} elapsed={elapsed:.3f}s events={events}")


asyncio.run(main())
