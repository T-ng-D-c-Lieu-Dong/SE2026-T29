"""VT-116 corrections: fail-closed API boundary and missing state transitions.

Spoofing tests characterize an OPEN limitation; they do not prove authentication.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import Appointment
from app.services.booking import BOOKING_TIMEZONE

pytestmark = pytest.mark.integration


def slot(days=12):
    return (datetime.now(BOOKING_TIMEZONE) + timedelta(days=days)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )


async def create(client, owner="alice", days=12, name="Same Name"):
    response = await client.post(
        "/api/appointments",
        headers={"X-User-Id": owner},
        json={"customer_name": name, "starts_at": slot(days).isoformat()},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize("route", ["list", "detail", "create", "cancel"])
async def test_private_routes_missing_identity_fail_closed(client, route):
    appointment_id = await create(client)
    if route == "list":
        response = await client.get("/api/appointments")
    elif route == "detail":
        response = await client.get(f"/api/appointments/{appointment_id}")
    elif route == "cancel":
        response = await client.delete(f"/api/appointments/{appointment_id}")
    else:
        response = await client.post(
            "/api/appointments",
            json={"customer_name": "Same Name", "starts_at": slot(13).isoformat()},
        )
    assert response.status_code == 401


@pytest.mark.parametrize("identity", ["   ", "x" * 101])
async def test_invalid_identity_is_rejected(client, identity):
    response = await client.get("/api/appointments", headers={"X-User-Id": identity})
    assert response.status_code == 401


async def test_same_customer_name_does_not_confer_ownership(client):
    alice_id = await create(client, "alice", 12)
    bob_id = await create(client, "bob", 13)
    response = await client.get("/api/appointments", headers={"X-User-Id": "bob"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [bob_id]
    response = await client.get(f"/api/appointments/{alice_id}", headers={"X-User-Id": "bob"})
    assert response.status_code == 404
    response = await client.delete(f"/api/appointments/{alice_id}", headers={"X-User-Id": "bob"})
    assert response.status_code == 403


async def test_payload_owner_cannot_override_caller(client):
    response = await client.post(
        "/api/appointments", headers={"X-User-Id": "bob"},
        json={"customer_name": "Alice", "owner_id": "alice", "starts_at": slot().isoformat()},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("owner", ["legacy_known_uuid", "unassigned", "anonymous"])
async def test_legacy_ownership_is_quarantined_even_when_identifier_is_known(
    client, test_session_factory, owner
):
    appointment_id = uuid4()
    async with test_session_factory() as session:
        session.add(Appointment(
            id=appointment_id, customer_name="Known Patient", owner_id=owner,
            starts_at=slot(), status="booked", is_deleted=False,
        ))
        await session.commit()
    # A valid caller cannot read the historical row.
    response = await client.get("/api/appointments", headers={"X-User-Id": "alice"})
    assert response.json()["items"] == []
    response = await client.get(
        f"/api/appointments/{appointment_id}", headers={"X-User-Id": "alice"}
    )
    assert response.status_code == 404
    # Knowing/asserting the stored historical owner never grants access.
    for method, path in [
        ("GET", "/api/appointments"),
        ("GET", f"/api/appointments/{appointment_id}"),
        ("GET", "/api/appointments/trash"),
        ("PATCH", f"/api/appointments/{appointment_id}/soft-delete"),
        ("PATCH", f"/api/appointments/{appointment_id}/restore"),
        ("DELETE", f"/api/appointments/{appointment_id}"),
    ]:
        response = await client.request(method, path, headers={"X-User-Id": owner})
        assert response.status_code == 401
    async with test_session_factory() as session:
        saved = await session.get(Appointment, appointment_id)
        assert saved.status == "booked"
        assert saved.is_deleted is False


async def test_forged_identity_still_reads_owner_data_without_gateway_OPEN_RISK(client):
    """PASS means the limitation was reproduced, NOT that spoofing was blocked."""
    appointment_id = await create(client, "alice")
    response = await client.get(
        f"/api/appointments/{appointment_id}", headers={"X-User-Id": "alice"}
    )
    assert response.status_code == 200
    assert response.json()["id"] == appointment_id


async def test_tc11_restore_past_booking_rejected_without_state_change(client, test_session_factory):
    appointment_id = UUID(await create(client))
    await client.patch(
        f"/api/appointments/{appointment_id}/soft-delete", headers={"X-User-Id": "alice"}
    )
    async with test_session_factory() as session:
        appointment = await session.get(Appointment, appointment_id)
        appointment.starts_at = datetime(2020, 1, 1, tzinfo=UTC)
        original_deleted_at = appointment.deleted_at
        await session.commit()
    response = await client.patch(
        f"/api/appointments/{appointment_id}/restore", headers={"X-User-Id": "alice"}
    )
    assert response.status_code == 422
    async with test_session_factory() as session:
        appointment = await session.get(Appointment, appointment_id)
        assert appointment.is_deleted is True
        assert appointment.deleted_at == original_deleted_at


async def test_cancelled_delete_restore_preserves_cancellation_and_free_slot(client):
    appointment_id = await create(client)
    response = await client.delete(
        f"/api/appointments/{appointment_id}", headers={"X-User-Id": "alice"}
    )
    assert response.status_code == 204
    deleted = await client.patch(
        f"/api/appointments/{appointment_id}/soft-delete", headers={"X-User-Id": "alice"}
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "cancelled"
    assert deleted.json()["is_deleted"] is True
    # Cancelled restoration must not claim a slot already rebooked by Bob.
    await create(client, "bob")
    restored = await client.patch(
        f"/api/appointments/{appointment_id}/restore", headers={"X-User-Id": "alice"}
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "cancelled"
    assert restored.json()["is_deleted"] is False
    assert restored.json()["deleted_at"] is None
    assert restored.json()["cancelled_at"] == deleted.json()["cancelled_at"]


async def test_cancel_soft_deleted_booking_returns_404(client):
    appointment_id = await create(client)
    await client.patch(
        f"/api/appointments/{appointment_id}/soft-delete", headers={"X-User-Id": "alice"}
    )
    response = await client.delete(
        f"/api/appointments/{appointment_id}", headers={"X-User-Id": "alice"}
    )
    assert response.status_code == 404
