"""Experiment (plan review R7): what can asyncio.timeout actually bound?

(a) a cooperative hang, (b) a blocking call inside ``async def``, (c) a coroutine that swallows
``CancelledError``.
"""

import asyncio
import time


async def coop_hang() -> None:
    await asyncio.Event().wait()


async def blocking() -> None:
    time.sleep(1.0)  # noqa: ASYNC251 - deliberate: e.g. requests.post / smtplib in async def


async def swallow() -> None:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        await asyncio.sleep(1.0)  # ignores cancellation and keeps "sending"


async def bounded(function, budget: float = 0.1) -> tuple[str, float]:
    started = time.perf_counter()
    try:
        async with asyncio.timeout(budget):
            await function()
        outcome = "completed"
    except TimeoutError:
        outcome = "TimeoutError"
    return outcome, time.perf_counter() - started


async def main() -> None:
    for function in (coop_hang, blocking, swallow):
        outcome, elapsed = await bounded(function)
        print(f"{function.__name__:10s} budget=0.100s outcome={outcome:12s} elapsed={elapsed:.3f}s")


asyncio.run(main())
