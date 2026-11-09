from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.services.booking import BOOKING_TIMEZONE

pytestmark = pytest.mark.integration


def future_slot(days: int = 3, hour: int = 14) -> datetime:
    day = datetime.now(BOOKING_TIMEZONE).date() + timedelta(days=days)
    return datetime.combine(day, datetime.min.time(), tzinfo=BOOKING_TIMEZONE).replace(hour=hour)


async def test_tc01_soft_delete_happy_path(client) -> None:
    slot = future_slot(days=3, hour=10)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    assert create_resp.status_code == 201
    apt_id = create_resp.json()["id"]

    delete_resp = await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["is_deleted"] is True
    assert data["deleted_at"] is not None

    # Bản ghi phải bị ẩn khỏi GET detail
    get_resp = await client.get(f"/api/appointments/{apt_id}", headers={"X-User-Id": "UserA"})
    assert get_resp.status_code == 404

    # Slot phải được giải phóng: Người khác có thể đặt vào đúng slot đó
    user_c_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserC", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserC"},
    )
    assert user_c_resp.status_code == 201


async def test_tc02_restore_happy_path(client) -> None:
    slot = future_slot(days=3, hour=11)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_id = create_resp.json()["id"]

    # Soft delete
    await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )

    # Restore khi slot vẫn còn trống
    restore_resp = await client.patch(
        f"/api/appointments/{apt_id}/restore",
        headers={"X-User-Id": "UserA"},
    )
    assert restore_resp.status_code == 200
    restored = restore_resp.json()
    assert restored["is_deleted"] is False
    assert restored["deleted_at"] is None

    # Kiểm tra đã xuất hiện lại ở GET detail
    get_resp = await client.get(f"/api/appointments/{apt_id}", headers={"X-User-Id": "UserA"})
    assert get_resp.status_code == 200


async def test_tc06_cross_user_soft_delete_forbidden(client) -> None:
    slot = future_slot(days=4, hour=10)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_id = create_resp.json()["id"]

    # User B cố xóa của User A
    attack_resp = await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserB"},
    )
    assert attack_resp.status_code == 403


async def test_tc07_cross_user_restore_forbidden(client) -> None:
    slot = future_slot(days=4, hour=11)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_id = create_resp.json()["id"]

    # User A soft delete
    await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )

    # User B cố restore của User A
    attack_resp = await client.patch(
        f"/api/appointments/{apt_id}/restore",
        headers={"X-User-Id": "UserB"},
    )
    assert attack_resp.status_code == 403


async def test_tc08_cross_user_get_detail_isolation(client) -> None:
    slot = future_slot(days=4, hour=14)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_id = create_resp.json()["id"]

    # User B cố đọc chi tiết appointment của User A
    resp = await client.get(f"/api/appointments/{apt_id}", headers={"X-User-Id": "UserB"})
    assert resp.status_code == 404


async def test_tc09_trash_api_isolation(client) -> None:
    slot_a = future_slot(days=5, hour=10)
    slot_b = future_slot(days=5, hour=11)

    resp_a = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot_a.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    resp_b = await client.post(
        "/api/appointments",
        json={"customer_name": "UserB", "starts_at": slot_b.isoformat()},
        headers={"X-User-Id": "UserB"},
    )
    apt_a = resp_a.json()["id"]
    apt_b = resp_b.json()["id"]

    # Cả hai đều xóa mềm booking của mình
    await client.patch(f"/api/appointments/{apt_a}/soft-delete", headers={"X-User-Id": "UserA"})
    await client.patch(f"/api/appointments/{apt_b}/soft-delete", headers={"X-User-Id": "UserB"})

    # User A xem trash
    trash_a = await client.get("/api/appointments/trash", headers={"X-User-Id": "UserA"})
    assert trash_a.status_code == 200
    items_a = trash_a.json()["items"]
    ids_a = [item["id"] for item in items_a]
    assert apt_a in ids_a
    assert apt_b not in ids_a


async def test_tc10_restore_slot_conflict_returns_409(client) -> None:
    slot = future_slot(days=6, hour=10)

    # User A đặt slot 10:00
    resp_a = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_a = resp_a.json()["id"]

    # User A xóa mềm (giải phóng slot)
    await client.patch(f"/api/appointments/{apt_a}/soft-delete", headers={"X-User-Id": "UserA"})

    # User C tranh thủ đặt vào slot 10:00 đó
    resp_c = await client.post(
        "/api/appointments",
        json={"customer_name": "UserC", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserC"},
    )
    assert resp_c.status_code == 201

    # User A cố gắng restore booking của mình -> Bắt buộc 409 Conflict
    conflict_resp = await client.patch(
        f"/api/appointments/{apt_a}/restore",
        headers={"X-User-Id": "UserA"},
    )
    assert conflict_resp.status_code == 409
    assert "already has an active booking" in conflict_resp.json()["detail"].lower()


async def test_tc04_tc05_idempotency_soft_delete_and_restore(client) -> None:
    slot = future_slot(days=6, hour=14)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_id = create_resp.json()["id"]

    # Soft delete lần 1
    resp1 = await client.patch(f"/api/appointments/{apt_id}/soft-delete", headers={"X-User-Id": "UserA"})
    assert resp1.status_code == 200
    deleted_at_1 = resp1.json()["deleted_at"]

    # Soft delete lần 2
    resp2 = await client.patch(f"/api/appointments/{apt_id}/soft-delete", headers={"X-User-Id": "UserA"})
    assert resp2.status_code == 200
    assert resp2.json()["deleted_at"] == deleted_at_1

    # Restore lần 1
    r_resp1 = await client.patch(f"/api/appointments/{apt_id}/restore", headers={"X-User-Id": "UserA"})
    assert r_resp1.status_code == 200

    # Restore lần 2
    r_resp2 = await client.patch(f"/api/appointments/{apt_id}/restore", headers={"X-User-Id": "UserA"})
    assert r_resp2.status_code == 200


async def test_tc12_soft_delete_not_found(client) -> None:
    random_id = uuid4()
    resp = await client.patch(
        f"/api/appointments/{random_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )
    assert resp.status_code == 404
