"""Verify real Alembic upgrades only against the isolated VT-116 final database."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ["TEST_DATABASE_URL"]
parsed = make_url(URL)
if (parsed.host, parsed.port, parsed.database) != ("127.0.0.1", 55433, "vt116_final_test"):
    raise SystemExit("Refusing any database except the isolated VT-116 final database")
os.environ["BOOKING_DATABASE_URL"] = URL


def migrate(revision):
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=ROOT / "backend",
        check=True,
    )


async def seed_or_verify(seed):
    engine = create_async_engine(URL)
    async with engine.begin() as connection:
        if seed:
            await connection.execute(
                text(
                    "INSERT INTO appointments (id, customer_name, starts_at) VALUES "
                    "('00000000-0000-0000-0000-000000000001', 'Legacy Patient', '2030-01-01T03:00Z')"
                )
            )
        else:
            row = (
                await connection.execute(
                    text("SELECT owner_id, owner_access_enabled FROM appointments")
                )
            ).one()
            assert row.owner_id == "legacy_00000000000000000000000000000001"
            assert row.owner_access_enabled is False
            revision = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar()
            assert revision == "20261109_0003"
            print("PASS: upgrade baseline -> 0002 -> 0003 preserves and quarantines legacy data")
    await engine.dispose()


migrate("20261007_0001")
asyncio.run(seed_or_verify(True))
migrate("head")
asyncio.run(seed_or_verify(False))
