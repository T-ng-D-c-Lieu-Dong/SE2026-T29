# VT-118 — Specification, invariant và review AI plan

Sinh viên: Phạm Minh Cương (23001840) · Nhóm SE2026-T29 · APP-03 Production Readiness Lab
Baseline: `5c8efc21e2a4eaf81d68325bc832098ffe5bf234` (main) · Nhánh: `feat/vt118-booking-notification-23001840`

## 1. Problem statement

Khi khách đặt lịch thành công (`POST /api/appointments` → 201) hệ thống hiện không phát ra bất kỳ thông báo
nào (`grep -rn notif backend/app` rỗng, xem `evidence/01-plan-review-experiments.log`). Cần phát sự kiện
nghiệp vụ `appointment.created` tới một kênh thông báo. Kênh thông báo là phụ thuộc bên ngoài không đáng tin
cậy: có thể ném lỗi, chậm hoặc treo. Lỗi hoặc độ chậm của kênh này không được làm mất hay rollback booking,
không được đổi mã 201, và không được kéo dài request vượt ngân sách độ trễ, kể cả khi đầu vào lớn hoặc có
60 request đồng thời.

## 2. Acceptance criteria (kiểm thử được)

| ID | Tiêu chí |
| --- | --- |
| AC1 | Booking hợp lệ được commit, notifier nhận **đúng 1** sự kiện `appointment.created` có `appointment_id`, `starts_at` (UTC) và `customer_name` của booking đã lưu; response 201 có `notification_status = "sent"`. |
| AC2 | Notifier ném exception → vẫn 201, booking tồn tại trong DB với `status = booked`, response `notification_status = "failed"`, có log cảnh báo `booking.notification.failed` chỉ chứa `appointment_id` và tên lớp lỗi (không chứa `customer_name` hay message của exception). |
| AC3 | Notifier không xong trong `BOOKING_NOTIFICATION_TIMEOUT_SECONDS` (mặc định 0.5 s, cho phép (0, 5]) → bị hủy khi hết hạn, vẫn 201, `notification_status = "timeout"`, request chỉ dài thêm tối đa khoảng timeout. |
| AC4 | Request không thành công (422 dữ liệu sai, 409 trùng slot, 500 fault injection) **không** phát thông báo và không ghi booking. |
| AC5 | `customer_name` vượt 100 ký tự, kể cả payload rất lớn (1 000 000 ký tự ≈ 1 MB), bị từ chối 422 trước khi chạm DB/notifier, trong < 1 s; tên hợp lệ ở biên 100 ký tự vẫn được gửi nguyên vẹn. |

## 3. Non-functional constraints

| ID | Ràng buộc | Cách kiểm chứng |
| --- | --- | --- |
| NFR1 | 60 tác vụ tạo booking đồng thời: p95 ≤ 2.0 s và 0 lỗi 5xx khi notifier bình thường, lỗi, hoặc treo; payload lớn bị từ chối với p95 ≤ 2.0 s. | Harness `loadtest/vt118/` (uvicorn + PostgreSQL thật). |
| NFR2 | Không giữ DB connection trong lúc chờ notifier (pool chỉ có 5 + 10 kết nối, `pool_timeout = 3 s`). | TC11 đo `pool.checkedout()` trong lúc notifier chạy. |
| NFR3 | Log về notification không chứa `customer_name` (cùng chính sách với request logging trong `backend/README.md`). | TC02. |
| NFR4 | Thay đổi API chỉ thêm field (additive), không cần migration (tuân `docs/releases/migration-policy.md`). | Test cũ giữ nguyên và vẫn pass. |

## 4. Invariant / contract quan trọng nhất

> **Kết quả của notification không bao giờ thay đổi kết quả của booking.** Booking đã commit ⇔ client nhận
> 201. Notification chỉ được phát **sau khi** transaction đã commit và đã trả connection về pool, tối đa
> một lần cho mỗi booking trong luồng request. Mọi lỗi `Exception` hoặc timeout của notifier được chuyển
> thành `notification_status`, không bao giờ thành 5xx. `asyncio.CancelledError` vẫn được truyền đi để
> shutdown và việc client hủy request còn hoạt động.

## 5. Review AI plan (`ai-plan-v1.md`) bằng repository thật

Evidence nằm trong `evidence/01-plan-review-experiments.log`; các script thí nghiệm ở `experiments/`.

| # | Điểm trong plan | Kết luận | Evidence |
| --- | --- | --- | --- |
| R1 | Queue `asyncio.Queue(1000)` + 2 worker chạy trong lifespan, fire-and-forget, sửa `conftest.py` để chạy lifespan. | **Bác bỏ cho slice này.** Thay bằng gọi notifier ngay trong request, có ngân sách thời gian (`asyncio.timeout`), và trả trạng thái qua field `notification_status`. | (a) `exp_a7_background_tasks.py`: `ASGITransport` **không** chạy lifespan (`events` không có `lifespan-startup`), nên worker sẽ không chạy trong mọi integration test hiện có nếu không sửa fixture chung. (b) Deploy/rollback recreate container (README mục đầu), nên queue trong RAM mất event đúng lúc drill. (c) Client không biết thông báo có tới hay không. (d) Plan sửa 15 file; slice chỉ cần 6 file code. |
| R2 | "Gọi notifier **sau `commit()` và `refresh()`**". | **Sửa.** Khi notifier được await trong request (R1), thứ tự `commit → refresh → notify` giữ 1 connection trong transaction đang mở suốt thời gian chờ. Đổi thành `flush → refresh → commit → notify`. | `exp_pool_hold_after_refresh.py`: `commit-then-refresh: checked_out_after=1 in_transaction=True`, `refresh-then-commit: checked_out_after=0`. Pool là `AsyncAdaptedQueuePool size=5 max_overflow=10 timeout=3.0`: 60 request × 0.5 s / 15 connection ≈ 2 s xếp hàng. |
| R3 | A3: "nginx mặc định 1 MB là giả định", hàm ý nginx chặn payload lớn. | **Sửa/khoanh phạm vi.** Production chỉ mở cổng web (`compose.production.yaml`: "No published port"), còn `deploy/compose.yaml` publish thẳng `8000:8000` và harness tải cũng gọi thẳng 8000. Vì vậy lớp chặn cần test là schema (`max_length = 100`) ở API, đo bằng payload 1 MB (TC13). Giới hạn 1 MB của nginx chưa được kiểm chứng trên demo host. | `grep` trong log: `deploy/compose.yaml-92- "${BACKEND_PORT:-8000}:8000"`; `nginx.conf` không có `client_max_body_size`. |
| R4 | `loadtest/notification.js` chạy k6, thêm `BOOKING_NOTIFICATION_FAULT_*` vào settings production. | **Bác bỏ.** k6 không có trong môi trường kiểm chứng. Thêm cấu hình fault cho notifier vào production cũng mở rộng bề mặt cấu hình không cần thiết. Thay bằng harness Python (`httpx` + `asyncio`, 60 worker) và launcher `loadtest/vt118/serve.py` gắn notifier giả **chỉ trong process tải**. | `which k6` → `k6: not installed`. |
| R5 | Unit test "submit 1 000 lần < 50 ms", "close < 0.5 s". | **Sửa.** Ngưỡng wall-clock chặt dễ gây flaky trên CI. Notifier treo được mô phỏng bằng `asyncio.Event()` không bao giờ set, timeout 0.05 s, và chỉ assert cận trên rộng (< 1 s). | Nguy cơ flaky dạng time; kiểm tra ở `evidence/06-flaky.log`. |
| R6 | A6/A7 (BackgroundTasks bị cộng vào thời gian request trong ASGI test) ghi là "giả định". | **Xác nhận bằng thí nghiệm**, giữ quyết định không dùng BackgroundTasks. | `status=200 elapsed=1.004s events=['bg-done']`: client chờ cả background task 1 s. |
| R7 | `try/except Exception`, không bắt `CancelledError`; không ghi PII; không migration; đỏ vì ImportError thì không tính; đo baseline trước. | **Chấp nhận**, đưa vào test TC02, TC07 và quy trình red (stub interface trước khi đếm red). | `exp_timeout_limits.py` còn chỉ ra giới hạn: timeout **không** chặn được notifier chặn event loop (`time.sleep`) hoặc nuốt `CancelledError` (`elapsed=1.000s`, `1.102s`). Đây là residual risk, xem TC18. |

### Plan sau review (được dùng để code)

1. `backend/app/services/notifications.py` (mới): `AppointmentCreatedEvent`, `BookingNotifier` (Protocol, async),
   `LoggingBookingNotifier` (mặc định, không log tên khách), `NotificationOutcome`,
   `notify_appointment_created(...)` bọc `asyncio.timeout` và `except Exception`.
2. `backend/app/services/booking.py`: `create()` đổi sang `refresh → commit`; thêm `create_and_notify()` trả
   `CreatedBooking(appointment, notification)`.
3. `backend/app/api/appointments.py`: dependency `get_booking_notifier`, response `AppointmentCreated` với
   `notification_status`, ánh xạ `NotificationOutcome → "sent" | "failed" | "timeout"`.
4. `backend/app/schemas/appointment.py`, `backend/app/config.py` (`notification_timeout_seconds`), `backend/app/main.py`.
5. Test: `backend/tests/unit/test_booking_notifications.py`, `backend/tests/integration/test_appointment_notifications.py`.
6. Harness tải: `loadtest/vt118/serve.py`, `loadtest/vt118/load_notifications.py`.
