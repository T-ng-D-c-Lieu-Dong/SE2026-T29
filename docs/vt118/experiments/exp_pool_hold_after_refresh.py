"""Experiment (plan review R2): after commit() then refresh(), is a pooled connection held?

Run from backend/ with BOOKING_DATABASE_URL pointing at a *_test database.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault(
    "BOOKING_DATABASE_URL", "postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test"
)

from app.db import Base, SessionFactory, engine  # noqa: E402
from app.models import Appointment  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def main() -> None:
    pool = engine.pool
    print(
        f"pool: {type(pool).__name__} size= {pool.size()} "
        f"max_overflow= {pool._max_overflow} timeout= {pool._timeout}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("TRUNCATE appointments"))
    base = datetime(2030, 1, 1, 3, 0, tzinfo=UTC)
    for offset, order in enumerate(("commit-then-refresh", "refresh-then-commit"), start=1):
        async with SessionFactory() as session:
            appointment = Appointment(customer_name="x", starts_at=base + timedelta(days=offset))
            session.add(appointment)
            await session.flush()
            if order == "commit-then-refresh":
                await session.commit()
                await session.refresh(appointment)
            else:
                await session.refresh(appointment)
                await session.commit()
            print(
                f"{order}: checked_out_after={pool.checkedout()} "
                f"in_transaction={session.in_transaction()} "
                f"created_at_loaded={appointment.created_at is not None}"
            )
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE appointments"))
    await engine.dispose()


asyncio.run(main())
