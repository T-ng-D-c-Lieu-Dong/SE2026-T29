"""Experiment (risk: large input): size and time of the 422 response for an oversized name.

Run from backend/. Does not need a database: validation fails before the session is used.
"""

import asyncio
import json
import time

from app.main import create_app
from httpx import ASGITransport, AsyncClient


async def main() -> None:
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        for chars in (101, 10_000, 1_000_000, 5_000_000):
            body = {"customer_name": "X" * chars, "starts_at": "2030-01-01T10:00:00+07:00"}
            started = time.perf_counter()
            response = await client.post("/api/appointments", json=body)
            elapsed_ms = (time.perf_counter() - started) * 1000
            detail = response.json()["detail"][0]
            echoed = detail.get("input")
            echoed_chars = len(echoed) if isinstance(echoed, str) else None
            print(
                f"name_chars={chars:>9} status={response.status_code} "
                f"request_bytes={len(json.dumps(body)):>9} "
                f"response_bytes={len(response.content):>9} "
                f"echoed_input_chars={echoed_chars} elapsed={elapsed_ms:.1f}ms "
                f"type={detail['type']}"
            )


asyncio.run(main())
