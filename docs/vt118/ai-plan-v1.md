# VT-118 — Implementation plan do coding agent tạo (bản gốc, chưa sửa)

- Công cụ: Claude (Cowork), agent loại `Plan` (chỉ đọc repository, không được sửa file).
- Thời điểm: 2026-11-07, trên baseline `5c8efc21e2a4eaf81d68325bc832098ffe5bf234` (main).
- Bản review và các điểm bị sửa/bác bỏ: xem [01-spec-plan-review.md](01-spec-plan-review.md).

## Prompt (nguyên văn)

```text
Bạn là coding agent. Repository: /home/claude/repo (FastAPI + SQLAlchemy async + PostgreSQL, dự án
"APP-03 – Production Readiness Lab", backend ở backend/app, tests ở backend/tests). KHÔNG sửa hoặc tạo
file nào; chỉ đọc code và trả về một IMPLEMENTATION PLAN.

Change request VT-118: "Thêm thông báo cho một sự kiện nghiệp vụ; lỗi gửi thông báo không được làm hỏng
giao dịch chính."
Risk trọng tâm: đầu vào lớn gây timeout hoặc suy giảm hiệu năng ngoài dự kiến.
Mức tải kiểm chứng: 60 người dùng/tác vụ đồng thời; mục tiêu p95 ≤ 2.0 giây.
Ràng buộc: test phải được viết TRƯỚC implementation và phải fail đúng lý do trước khi sửa code.

Hãy trả về (tiếng Việt, tối đa ~600 từ):
1. Sự kiện nghiệp vụ bạn chọn và lý do.
2. Các bước triển khai một vertical slice nhỏ.
3. Danh sách assumptions (đánh số A1, A2, ...), ghi rõ cái nào bạn đã kiểm tra trong code và cái nào
   chỉ là giả định.
4. Danh sách chính xác các file dự định tạo/sửa.
5. Các test sẽ viết trước và vì sao chúng fail trước patch.
6. Cách đảm bảo lỗi/timeout của notification không ảnh hưởng transaction đặt lịch và độ trễ p95 (nêu cụ
   thể cơ chế, vị trí gọi notification so với commit, cách xử lý exception/timeout, có dùng
   BackgroundTasks hay không).
7. Cách chạy test tích hợp và test tải.
```

## Output của agent (nguyên văn, chỉ định dạng lại Markdown)

### 1. Sự kiện nghiệp vụ
Chọn **`appointment.created`**: phát khi `POST /api/appointments` trả 201, sau khi commit xong.
- Đây là luồng ghi được dùng nhiều nhất. `booking.js` đã đo tải luồng này, và đã có test cho 201/409/422/fault.
- Không phát cho 409, 422 hay `InjectedBookingFault`.
- Không chọn hủy lịch, vì `cancel` idempotent: lần hủy thứ hai cũng trả 204, nên phải thêm logic chống gửi trùng.

### 2. Các bước
1. Viết test (mục 5) rồi chạy. Kết quả ImportError là đỏ sai lý do, không tính.
2. Thêm khung rỗng, chưa có hành vi: `NotificationSender` (Protocol), `AppointmentCreatedEvent` (frozen dataclass, chỉ chứa giá trị nguyên thủy), `NotificationDispatcher` với `submit/start/close` không làm gì, tham số `BookingService(notifier=None)`, và `app.state.notifications`. Test cũ vẫn xanh; test mới đỏ bằng AssertionError. Lưu output lần chạy này.
3. Viết dispatcher thật, gọi nó sau commit, nối vào lifespan, thêm settings.
4. Chạy unit và integration cho xanh, rồi chạy k6 với 60 VU.
5. Cập nhật `.env.example`, compose local, README loadtest và evidence.

### 3. Assumptions
- **A1 [đã kiểm]** Backend chưa có notification nào.
- **A2 [đã kiểm]** `customer_name` tối đa 100 ký tự (schema + cột `String(100)`). Event lấy dữ liệu từ ORM sau `refresh`, không lấy từ body thô.
- **A3 [đã kiểm]** App không giới hạn kích thước body. `nginx.conf` không đặt `client_max_body_size`; việc nginx mặc định 1 MB là giả định.
- **A4 [đã kiểm]** Uvicorn chạy một process (không có `--workers`), nên queue trong process dùng được.
- **A5 [đã kiểm]** Alert `HighLatencyP95` (>0.5s) tính từ histogram phía server `http_server_duration_milliseconds`. Repo có cơ chế kích hoạt rollback từ alert.
- **A6 [giả định; môi trường không cài FastAPI nên chưa chạy thử]** Middleware OTel ASGI ghi duration khi app return, nên thời gian chạy BackgroundTasks bị cộng vào p95 phía server.
- **A7 [giả định]** httpx `ASGITransport` chờ app return, kể cả background tasks, và không chạy lifespan.
- **A8 [đã kiểm]** Engine dùng pool mặc định (giả định 5+10 kết nối), `pool_timeout=3s`. Với 60 VU, ngay bản gốc có thể đã có 5xx, nên phải đo baseline trước.
- **A9 [giả định]** Chưa có kênh gửi thật, nên dùng `LoggingNotificationSender`. Gửi theo kiểu best-effort: thông báo đang xếp hàng bị mất khi restart; outbox để sau.
- **A10 [đã kiểm]** Event loop của test có scope session, nên phải đóng worker trong teardown.

### 4. File
**Tạo mới:** `backend/app/services/notifications.py`, `backend/tests/unit/test_notification_dispatcher.py`,
`backend/tests/unit/test_booking_notifications.py`, `backend/tests/integration/test_appointment_notifications.py`,
`loadtest/notification.js`.

**Sửa:** `backend/app/services/booking.py`, `backend/app/services/__init__.py`,
`backend/app/api/appointments.py` (lấy dispatcher từ `request.app.state`, giống `get_telemetry_runtime`),
`backend/app/main.py`, `backend/app/config.py`, `backend/tests/integration/conftest.py` (fixture dùng
`app.router.lifespan_context`), `backend/.env.example`, `deploy/compose.yaml`, `loadtest/README.md`, `Makefile`.
Không cần migration.

### 5. Test viết trước (đỏ vì khung rỗng không gọi notifier, các bộ đếm đều bằng 0)
**Dispatcher:** sender treo, timeout 0.05s → `timed_out==1`, event sau vẫn được gửi; sender raise một lần →
`failed==1`, `sent==1`; queue 10 chỗ, sender treo, `submit` 1.000 lần: tổng thời gian <50 ms, `dropped≥989`;
`close(drain_timeout=0.1)` xong trong <0.5s và sender nhận `CancelledError`.

**Service:** thứ tự gọi là `create, commit, refresh, notify` (đỏ vì thiếu `notify`); `submit` raise, booking vẫn
trả về, `attempts==1` (đỏ vì `attempts==0`).

**Integration (PostgreSQL thật):** sender mở session mới và thấy row (chứng minh gửi sau commit); sender lỗi:
vẫn 201, row tồn tại, `failed==1`; `wait_for(post, 2s)` thành công trong khi sender đang treo (theo A7, test này
cũng sẽ đỏ nếu ai đó đổi sang BackgroundTasks).

**Guard (xanh cả trước và sau patch, không tính là test đỏ):** 409/422/fault không tạo notification;
`customer_name` 1 MB trả 422 trong <2s và không có notification.

### 6. Cô lập lỗi và độ trễ
- Gọi `notifier.submit(event)` trong `BookingService.create`, **sau `commit()` và `refresh()`**. Lỗi notifier không thể rollback giao dịch, và đường lỗi 409 không bao giờ tới chỗ phát event.
- `submit` là lời gọi đồng bộ `put_nowait` vào `asyncio.Queue(maxsize=1000)`, bọc `try/except Exception` (không bắt `CancelledError`). Khi lỗi chỉ ghi log `appointment_id`, không ghi PII. Queue đầy thì bỏ event và tăng bộ đếm `dropped`.
- Hai worker cố định khởi động trong lifespan. Mỗi lần gửi bọc `asyncio.timeout(1.0)`; bắt `TimeoutError`/`Exception` để đếm, ghi log, rồi đi tiếp. Không retry. Payload tối đa 512 byte. Khi tắt: chờ queue cạn tối đa 2s rồi cancel worker.
- **Không dùng BackgroundTasks**: không giới hạn số task, không có backpressure khi sender treo; theo A6, làm tăng p95 phía server, có thể kích hoạt `HighLatencyP95` rồi dẫn tới rollback; theo A7, test ASGI không phân biệt được hai cách.
- Để đo tải, thêm `BOOKING_NOTIFICATION_FAULT_MODE/RATE/UNTIL/LATENCY_SECONDS`, dùng lại `BookingFaultInjector` để bọc sender và bắt buộc có `UNTIL`.

### 7. Cách chạy
```bash
docker compose -f backend/compose.test.yaml up -d --wait
(cd backend && BOOKING_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test alembic upgrade head)
TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test pytest -v backend/tests/unit backend/tests/integration
k6 run -e VUS=60 -e DURATION=2m -e TARGET_DATE=YYYY-MM-DD loadtest/notification.js
```
Threshold: POST `p(95)<2000`, `http_server_errors<1%`, `checks>99%`; chạy baseline trước patch, fault `off`,
`latency` 5s, `error`. Đạt khi mọi lần chạy p95 ≤ 2s, log `timed_out`/`failed` đúng cấu hình, số row khớp số 201.
