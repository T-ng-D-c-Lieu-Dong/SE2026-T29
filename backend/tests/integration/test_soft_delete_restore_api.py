import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import Appointment, AppointmentStatus
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
    resp1 = await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )
    assert resp1.status_code == 200
    deleted_at_1 = resp1.json()["deleted_at"]

    # Soft delete lần 2
    resp2 = await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["deleted_at"] == deleted_at_1

    # Restore lần 1
    r_resp1 = await client.patch(
        f"/api/appointments/{apt_id}/restore",
        headers={"X-User-Id": "UserA"},
    )
    assert r_resp1.status_code == 200

    # Restore lần 2
    r_resp2 = await client.patch(
        f"/api/appointments/{apt_id}/restore",
        headers={"X-User-Id": "UserA"},
    )
    assert r_resp2.status_code == 200


async def test_tc12_soft_delete_not_found(client) -> None:
    random_id = uuid4()
    resp = await client.patch(
        f"/api/appointments/{random_id}/soft-delete",
        headers={"X-User-Id": "UserA"},
    )
    assert resp.status_code == 404


# =========================================================================
# CÁC TEST CASES MỚI KIỂM CHỨNG THEO YÊU CẦU PHẢN BIỆN CHECKPOINT 2
# =========================================================================


async def test_auth_missing_header_returns_401(client) -> None:
    """Rủi ro 1: Thiếu thông tin xác thực danh tính caller phải bị từ chối 401."""
    random_id = uuid4()

    # Soft delete không có header
    resp_del = await client.patch(f"/api/appointments/{random_id}/soft-delete")
    assert resp_del.status_code == 401
    assert "Authentication required" in resp_del.json()["detail"]

    # Restore không có header
    resp_res = await client.patch(f"/api/appointments/{random_id}/restore")
    assert resp_res.status_code == 401
    assert "Authentication required" in resp_res.json()["detail"]

    # Trash không có header
    resp_trash = await client.get("/api/appointments/trash")
    assert resp_trash.status_code == 401


async def test_auth_header_spoofing_limitation_demonstration(client) -> None:
    """Rủi ro 1 & Giới hạn: Khi client tự giả mạo header của User A mà không có API Gateway,
    hệ thống backend thuần túy chỉ có thể tin vào header được inject.
    Test này chứng minh rằng việc bảo vệ chống Header Spoofing bắt buộc phải do Gateway."""
    slot = future_slot(days=7, hour=10)
    create_resp = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_id = create_resp.json()["id"]

    # User B cố tình gửi header X-User-Id: UserA (giả mạo ở tầng client HTTP thuần túy)
    spoofed_resp = await client.patch(
        f"/api/appointments/{apt_id}/soft-delete",
        headers={"X-User-Id": "UserA"},  # Giả mạo
    )
    # Vì backend tin cậy header từ upstream, thao tác sẽ được chấp nhận nếu header là UserA
    assert spoofed_resp.status_code == 200


async def test_concurrent_restore_same_slot_race_condition(client, test_session_factory) -> None:
    """Rủi ro 3: Hai request đồng thời cùng restore vào 1 slot bị trùng.
    Partial Unique Index bảo đảm đúng 1 request thành công và request kia nhận 409 Conflict."""
    slot = future_slot(days=8, hour=10)

    # Tạo 2 booking trên 2 thời điểm khác nhau ban đầu, rồi soft-delete cả 2
    resp1 = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt1_id = resp1.json()["id"]
    await client.patch(f"/api/appointments/{apt1_id}/soft-delete", headers={"X-User-Id": "UserA"})

    # Vì slot đã giải phóng, User B có thể tạo booking thứ 2 tại cùng slot đó
    resp2 = await client.post(
        "/api/appointments",
        json={"customer_name": "UserB", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserB"},
    )
    apt2_id = resp2.json()["id"]
    await client.patch(f"/api/appointments/{apt2_id}/soft-delete", headers={"X-User-Id": "UserB"})

    # Lúc này cả apt1 và apt2 đều đang SOFT_DELETED trên cùng slot.
    # Bây giờ User A và User B cùng gửi request RESTORE ĐỒNG THỜI:
    res1, res2 = await asyncio.gather(
        client.patch(f"/api/appointments/{apt1_id}/restore", headers={"X-User-Id": "UserA"}),
        client.patch(f"/api/appointments/{apt2_id}/restore", headers={"X-User-Id": "UserB"}),
    )

    # Đảm bảo 1 request thành công 200, 1 request bị từ chối 409 Conflict
    status_codes = sorted([res1.status_code, res2.status_code])
    assert status_codes == [200, 409], f"Expected [200, 409] but got {status_codes}"

    # Kiểm tra database: Đúng 1 booking duy nhất có status = 'booked' AND is_deleted = false
    async with test_session_factory() as session:
        active_count = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.starts_at == slot,
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.is_deleted.is_(False),
            )
        )
        assert active_count == 1


async def test_concurrent_booking_and_restore_same_slot(client, test_session_factory) -> None:
    """Rủi ro 3: 1 request tạo mới booking + 1 request restore cùng 1 slot đồng thời."""
    slot = future_slot(days=9, hour=10)

    # User A đặt rồi soft delete
    resp_a = await client.post(
        "/api/appointments",
        json={"customer_name": "UserA", "starts_at": slot.isoformat()},
        headers={"X-User-Id": "UserA"},
    )
    apt_a_id = resp_a.json()["id"]
    await client.patch(f"/api/appointments/{apt_a_id}/soft-delete", headers={"X-User-Id": "UserA"})

    # User C tạo mới ĐỒNG THỜI với User A restore
    res_create, res_restore = await asyncio.gather(
        client.post(
            "/api/appointments",
            json={"customer_name": "UserC", "starts_at": slot.isoformat()},
            headers={"X-User-Id": "UserC"},
        ),
        client.patch(
            f"/api/appointments/{apt_a_id}/restore",
            headers={"X-User-Id": "UserA"},
        ),
    )

    # Một request thành công (201 cho create hoặc 200 cho restore), request kia nhận 409 Conflict
    assert 409 in [res_create.status_code, res_restore.status_code]
    success_codes = [c for c in [res_create.status_code, res_restore.status_code] if c != 409]
    assert success_codes in [[200], [201]]

    # DB chỉ có duy nhất 1 booking active
    async with test_session_factory() as session:
        active_count = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.starts_at == slot,
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.is_deleted.is_(False),
            )
        )
        assert active_count == 1
