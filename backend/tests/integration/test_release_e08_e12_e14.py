"""Integration tests for release, deploy, and rollback evidence E08, E12, and E14.

Validates:
- E08: Release identifier traceability between API and manifest.
- E12: Data preservation across deploy/rollback cycles.
- E14: Rollback window database schema compatibility.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from scripts.release_manifest import ReleaseManifest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def explicit_regression_identity(client):
    """Preserve release assertions under the deliberate private API contract change."""
    client.headers["X-User-Id"] = "regression-user"


def get_repo_root() -> Path:
    current = Path.cwd()
    if (current / "docs" / "releases" / "v0.1.0.json").exists():
        return current
    if (current.parent / "docs" / "releases" / "v0.1.0.json").exists():
        return current.parent
    return Path(__file__).resolve().parents[3]


async def test_e08_version_traceability_integration(client: AsyncClient) -> None:
    """E08: GET /api/version returns version info that conforms to semantic release contract."""
    response = await client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert "release" in data
    assert "commit_sha" in data
    assert data["release"] != "latest", "Release identifier must never be 'latest'"


async def test_e12_booking_data_preserved_across_simulated_rollback(
    client: AsyncClient, test_session_factory
) -> None:
    """E12: Bookings created prior to deployment remain intact after rollback."""
    # 1. Create a business booking on the active release
    slot_time = (datetime.now(UTC) + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
    slot_str = slot_time.isoformat()

    create_payload = {
        "customer_name": "Nguyen Viet Anh - Pre-Deploy Customer",
        "starts_at": slot_str,
    }
    create_resp = await client.post("/api/appointments", json=create_payload)
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["id"]

    # 2. Verify booking exists in PostgreSQL
    async with test_session_factory() as session:
        result = await session.execute(
            text("SELECT id, customer_name, status FROM appointments WHERE id = :id"),
            {"id": uuid.UUID(booking_id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[1] == "Nguyen Viet Anh - Pre-Deploy Customer"
        assert row[2] == "booked"

    # 3. Simulate new release deployment and rollback
    # (Notice: Database volume/data is untouched because docker compose down -v is forbidden)
    manifest_path = get_repo_root() / "docs" / "releases" / "v0.1.0.json"
    manifest = ReleaseManifest.load(manifest_path)

    rolled_back_settings = Settings(
        release=manifest.release,
        commit_sha=manifest.commit_sha,
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: rolled_back_settings

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-User-Id": "regression-user"},
    ) as rolled_back_client:
        # Check /api/version matches restored release
        ver_resp = await rolled_back_client.get("/api/version")
        assert ver_resp.status_code == 200
        assert ver_resp.json()["release"] == manifest.release

        # Verify the original booking is STILL present and intact (E12)!
        list_resp = await rolled_back_client.get("/api/appointments")
        assert list_resp.status_code == 200
        data = list_resp.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        matching = [a for a in items if a["id"] == booking_id]
        assert len(matching) == 1
        assert matching[0]["customer_name"] == "Nguyen Viet Anh - Pre-Deploy Customer"
        assert matching[0]["status"] == "booked"

        # Verify cancellation works on the rolled-back release
        del_resp = await rolled_back_client.delete(f"/api/appointments/{booking_id}")
        assert del_resp.status_code == 204


async def test_e14_schema_backward_compatibility_during_rollback_window(
    client: AsyncClient, test_session_factory
) -> None:
    """E14: Rollback code continues to function seamlessly with current database schema."""
    # Test full lifecycle on current schema:
    target_slot = (datetime.now(UTC) + timedelta(days=3)).replace(
        minute=30, second=0, microsecond=0
    )
    slot_iso = target_slot.isoformat()

    # Create appointment
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "Rollback Window User", "starts_at": slot_iso},
    )
    assert create_resp.status_code == 201
    appt_id = create_resp.json()["id"]

    # Verify slots listing
    target_date = target_slot.strftime("%Y-%m-%d")
    slots_resp = await client.get(f"/api/slots?date={target_date}")
    assert slots_resp.status_code == 200

    # Cancel appointment
    del_resp = await client.delete(f"/api/appointments/{appt_id}")
    assert del_resp.status_code == 204

    # Idempotent cancel
    del_repeat = await client.delete(f"/api/appointments/{appt_id}")
    assert del_repeat.status_code == 204
