> HISTORICAL BASELINE / ORIGINAL PLAN. Final corrections, current ownership policy and verified results are in `final-correction-plan.md`, `README.md`, `test-strategy.md` and `traceability-and-ai-log.md`. Original assumptions and results below are retained for provenance, not current safety claims.

# BẢN GHI KHẢO SÁT REPOSITORY (REPOSITORY AUDIT) & ĐẶC TẢ NGHIỆP VỤ (SPECIFICATION)
**Bài tập cá nhân 3 — VT-116 | Production Readiness Lab (APP-03)**
- **Sinh viên thực hiện**: Nguyễn Việt Anh (MSSV: 23001827)
- **Nhóm**: SE2026-T29
- **Repository**: `https://github.com/CuongMotNang/SE2026-T29.git`
- **Baseline Commit SHA**: `8fe9de89b719bde237a118e18a671db1d3dfd6cd`
- **Working Branch**: `bt3/23001827-vt116-soft-delete-restore`

---

## 1. KẾT QUẢ KHẢO SÁT HIỆN TRẠNG REPOSITORY (AUDIT)

### 1.1. Công nghệ và Stack thực tế
- **Framework & Runtime**: Python 3.12+ (hệ thống chạy Python 3.14.4), FastAPI 0.162.2, Starlette 1.10.0, Pydantic 2.14.3 / Pydantic-Settings 2.16.2.
- **ORM & Database**: SQLAlchemy 2.1.8 (AsyncIO), PostgreSQL 18-alpine (chạy qua Docker Compose `backend/compose.test.yaml`), `asyncpg` 0.32.0 driver.
- **Database Migration**: Alembic 1.20.1 (đã có migration ban đầu `20261007_0001_create_appointments.py`).
- **Telemetry & Logging**: OpenTelemetry SDK 1.45.2 (FastAPI, SQLAlchemy, Logging instrumentation), OTLP/gRPC exporter.
- **Testing Framework**: Pytest 9.2.0, `pytest-asyncio` 1.4.1.post1, `httpx` 0.28.1.
- **Containerization**: Docker Compose v2 (v5.6.1), Docker Engine 29.9.2.

### 1.2. Cấu trúc Module liên quan
Mã nguồn backend tuân thủ kiến trúc Modular Monolith phân tầng rõ ràng tại `backend/app/`:
- `models/appointment.py`: Khai báo SQLAlchemy model `Appointment` và Enum `AppointmentStatus`.
- `schemas/appointment.py`: Pydantic schema validation (`AppointmentCreate`, `AppointmentRead`, `AppointmentList`, `SlotRead`).
- `repositories/appointments.py`: Lớp trừu tượng truy cập dữ liệu `AppointmentRepository` (thực hiện raw queries, async session management).
- `services/booking.py`: Business logic layer `BookingService` (chuẩn hóa múi giờ `Asia/Ho_Chi_Minh`, kiểm tra slot boundary 30 phút, slot tương lai, fault injection, telemetry spans).
- `api/appointments.py`: FastAPI Router định nghĩa các HTTP endpoints (`POST /api/appointments`, `GET /api/appointments`, `DELETE /api/appointments/{id}`).
- `domain/errors.py`: Định nghĩa ngoại lệ domain (`BookingError`, `InvalidSlot`, `SlotAlreadyBooked`, `AppointmentNotFound`).

### 1.3. Entity, Quan hệ dữ liệu và Database Constraints
Hiện tại repository chỉ có duy nhất một bảng thực thể nghiệp vụ: `appointments`.
- **Cấu trúc bảng**:
  - `id`: UUID (Primary Key, sinh ngẫu nhiên `uuid.uuid4`).
  - `customer_name`: String(100), không rỗng.
  - `starts_at`: DateTime(timezone=True), mốc thời gian bắt đầu hẹn.
  - `status`: String(16), mặc định `'booked'`.
  - `created_at`: DateTime(timezone=True), `server_default=now()`.
  - `cancelled_at`: DateTime(timezone=True), nullable.
- **Constraints & Indexes**:
  - `ck_appointments_status`: `CheckConstraint("status IN ('booked', 'cancelled')")`.
  - `uq_appointments_active_starts_at`: Partial Unique Index trên `starts_at` với điều kiện `WHERE status = 'booked'`. Đây là chốt chặn quan trọng nhất ở tầng DB để ngăn race condition khi hai request cùng đặt một slot.
  - `ix_appointments_starts_at`: B-tree Index trên `starts_at`.

### 1.4. API và Business Rules hiện có
1. `GET /api/slots?date=YYYY-MM-DD`: Liệt kê các slot trống trong ngày (mỗi slot 30 phút, bắt đầu tại :00 hoặc :30, nằm trong tương lai và chưa có booking `booked`).
2. `POST /api/appointments`: Đặt lịch hẹn mới.
   - Bắt buộc `customer_name` không được để trống (sau khi strip).
   - `starts_at` phải có UTC offset, chia hết cho 30 phút, và phải ở tương lai so với thời điểm đặt.
   - Trả về `201 Created` nếu thành công.
   - Trả về `409 Conflict` nếu slot đã có lịch `booked` khác.
   - Trả về `422 Unprocessable Entity` nếu dữ liệu hoặc slot không hợp lệ.
3. `GET /api/appointments`: Lấy danh sách toàn bộ lịch hẹn (hỗ trợ `limit`, `offset`). Hiện tại trả về tất cả bản ghi không phân biệt trạng thái hay người sở hữu.
4. `DELETE /api/appointments/{id}`: Hủy lịch hẹn (Cancel).
   - Nếu tồn tại: cập nhật `status = 'cancelled'`, `cancelled_at = now()`, trả về `204 No Content`.
   - Idempotent: nếu đã `cancelled`, gọi lại vẫn trả về `204 No Content`.
   - Nếu không tìm thấy: trả về `404 Not Found`.
   - Giải phóng slot cho người khác đặt lại.

### 1.5. Khảo sát Authentication & Authorization hiện tại
- **Thực tế source code**: Hoàn toàn **chưa có module Authentication / Authorization**. Không có bảng `users`, không có Bearer token, không có Session cookie.
- **Bằng chứng tài liệu**: `docs/architecture/architecture-context.md` (mục 3, dòng 24) xác nhận rõ:
  > *"MVP dùng dữ liệu giả trong môi trường demo giới hạn truy cập. Chưa có tài khoản khách hàng; các thao tác xem/hủy thuộc lịch dùng chung. Cần thiết kế danh tính và quyền sở hữu booking trước khi mở dịch vụ cho khách hàng thật."*
- **Khoảng trống bảo mật (Security Gap)**: Bất kỳ ai cũng có thể đọc danh sách toàn bộ appointments và hủy bất kỳ appointment nào của người khác nếu biết UUID. Điều này đối lập trực tiếp với Risk trọng tâm của VT-116.

### 1.6. Khảo sát Bộ Test hiện hữu và Môi trường chạy
- **Unit tests**: 65 test cases (`backend/tests/unit/`) kiểm tra booking service, deploy/rollback, manifest, telemetry, fault injection. Tất cả 65 tests PASS trong 2.15s (không cần DB).
- **Integration tests**: 14 test cases (`backend/tests/integration/`) kiểm tra API create booking, race condition đồng thời, idempotency của cancel, health check, release contract. Tất cả 14 tests PASS trong 0.34s với PostgreSQL 18-alpine test container (`compose.test.yaml`).
- **Tổng cộng**: 79 tests đang PASS 100% trên baseline commit `8fe9de89b719bde237a118e18a671db1d3dfd6cd`.

---

## 2. XÁC ĐỊNH VERTICAL SLICE CHO VT-116 (KẾT HỢP CHỈ ĐẠO CỦA SINH VIÊN)

### 2.1. Lựa chọn Resource
- Resource được chọn: **`Appointment`** (Booking). Đây là resource duy nhất và cốt lõi có vòng đời nghiệp vụ trong hệ thống hiện tại.
- Để đáp ứng Risk trọng tâm về **Phân quyền và Bảo mật cách ly giữa người dùng (Cross-user isolation)** mà không phá vỡ kiến trúc tối giản hiện có:
  - Bổ sung trường sở hữu `owner_id: str` (định danh người dùng sở hữu booking, ánh xạ hoặc tương thích với `customer_name` / User identity).
  - Bổ sung cơ chế Caller Context (nhận diện qua HTTP Header `X-User-Id` ở boundary API, giả lập người dùng đã xác thực User A / User B).
  - Phân quyền nghiêm ngặt: Chỉ chủ sở hữu (`owner_id == caller_id`) mới có quyền xem, xóa mềm, hoặc khôi phục appointment của mình.

### 2.2. Vòng đời Xóa mềm (Soft Delete) & Khôi phục (Restore) theo Quyết định của Sinh viên
Căn cứ quyết định bác bỏ cả 2 giả định A và B của sinh viên Nguyễn Việt Anh tại Checkpoint 1:
1. **Soft Delete giải phóng Slot**: Khi một booking bị soft delete (`is_deleted = True`), slot thời gian tương ứng **phải được giải phóng** khỏi tập các lịch đang chiếm dụng. Người khác được phép đặt vào slot này. Ràng buộc partial unique index ở DB phải được điều chỉnh để chỉ kiểm tra unique khi `status = 'booked' AND is_deleted = false`.
2. **Ẩn hoàn toàn khỏi API đọc thông thường**: Bản ghi đã soft delete phải bị loại khỏi cả danh sách (`GET /api/appointments`) và chi tiết (`GET /api/appointments/{id}` trả về `404 Not Found`).
3. **API Thùng rác riêng có xác thực**: Để xem các lịch hẹn đã soft delete, người dùng phải gọi endpoint riêng `GET /api/appointments/trash`, hệ thống chỉ trả về các lịch đã xóa thuộc sở hữu của chính người gọi.
4. **Kiểm tra xung đột slot khi Restore (Conflict Resolution)**: Khi restore, nếu slot đã bị người khác đặt mất hoặc đã trôi qua thời gian hiện tại, hệ thống từ chối khôi phục và trả về `409 Conflict`. Nếu slot còn trống, khôi phục thành công (`is_deleted = False`, `deleted_at = None`).

---

## 3. ĐẶC TẢ NGHIỆP VỤ (SPECIFICATION)

### 3.1. Problem Statement
Hệ thống hiện tại thiếu cơ chế bảo vệ xóa dữ liệu an toàn (chỉ có thao tác hủy nghiệp vụ, không có xóa mềm và khôi phục), đồng thời thiếu cơ chế phân quyền sở hữu tài nguyên (bất kỳ client nào cũng có thể đọc và thao tác trên mọi lịch hẹn). Điều này tạo ra rủi ro nghiêm trọng (**RISK-01**): người dùng có thể vô tình hoặc cố ý truy cập, xóa mềm, hoặc khôi phục dữ liệu thuộc về người dùng khác, gây rò rỉ thông tin cá nhân và làm vỡ tính nhất quán của dữ liệu đặt lịch.

### 3.2. Acceptance Criteria (AC)

- **AC-01 (Soft Delete & Slot Release)**: Khi chủ sở hữu hợp lệ (User A) gửi yêu cầu xóa mềm appointment của mình (`PATCH /api/appointments/{id}/soft-delete`), hệ thống đánh dấu bản ghi đã xóa mềm (`is_deleted = True`, `deleted_at = now()`), trả về HTTP `200 OK`. Slot thời gian được giải phóng để người khác có thể đặt. Bản ghi bị ẩn hoàn toàn khỏi danh sách `GET /api/appointments` và chi tiết `GET /api/appointments/{id}` (trả về `404 Not Found`).
- **AC-02 (Restore to Active Slot)**: Khi chủ sở hữu hợp lệ (User A) gửi yêu cầu khôi phục appointment đã xóa mềm (`PATCH /api/appointments/{id}/restore`), nếu slot thời gian vẫn còn trống trong tương lai, hệ thống khôi phục bản ghi (`is_deleted = False`, `deleted_at = None`), trả về HTTP `200 OK`. Appointment tái xuất hiện trong danh sách lịch hẹn của User A.
- **AC-03 (Slot Conflict Prevention on Restore)**: Nếu trong thời gian appointment A bị soft delete, slot `starts_at` đã bị người dùng khác đặt, khi User A yêu cầu restore, hệ thống phải phát hiện xung đột và từ chối khôi phục với mã lỗi `409 Conflict` kèm thông báo lỗi rõ ràng. Không cho phép ghi đè hay vi phạm ràng buộc duy nhất slot.
- **AC-04 (Cross-User Authorization Isolation)**: Nếu User B cố gắng truy cập chi tiết (`GET`), xóa mềm (`PATCH .../soft-delete`), hoặc khôi phục (`PATCH .../restore`) appointment thuộc sở hữu của User A, hệ thống phải từ chối truy cập với mã lỗi `403 Forbidden` (hoặc `404 Not Found` để chống enumeration attack). Dữ liệu của User A tuyệt đối không bị sửa đổi hoặc rò rỉ cho User B.
- **AC-05 (Dedicated Trash API with Ownership Filter)**: Cung cấp endpoint riêng `GET /api/appointments/trash` cho phép người dùng xem các booking đã bị soft delete của chính mình. Tuyệt đối không trả về booking đã xóa của người dùng khác.
- **AC-06 (Idempotency & State Transition Consistency)**: Việc thực hiện soft delete liên tiếp 2 lần trên cùng một resource hoặc restore liên tiếp 2 lần trên cùng một resource phải bảo toàn tính nhất quán trạng thái, không làm sai lệch mốc thời gian `deleted_at` hoặc gây lỗi hệ thống.

### 3.3. Non-Functional Constraints (NFC)

- **NFC-01 (Performance & Concurrency Constraint — Chuẩn VT-116)**: Hệ thống phải duy trì khả năng đáp ứng ổn định dưới tải **40 concurrent users/tasks đồng thời**, độ trễ phân vị **p95 ≤ 1.5 giây (1500 ms)** cho toàn bộ các thao tác nghiệp vụ đặt lịch, soft delete và restore.
- **NFC-02 (Database Integrity & Invariant Preservation)**: Ràng buộc tính nhất quán dữ liệu ở tầng cơ sở dữ liệu (Database-level Invariant) phải luôn được bảo toàn: Partial unique constraint đảm bảo không bao giờ tồn tại hai active booking trùng `starts_at`. Mọi thay đổi trạng thái phải được gói gọn trong ACID database transaction.

### 3.4. Các Bất biến cốt lõi (Core Business & Safety Invariants)

- **INV-01 (Single Active Booking per Slot Invariant)**:
  $$\forall a_1, a_2 \in \text{Appointments}: (a_1.\text{starts\_at} = a_2.\text{starts\_at} \land a_1.\text{status} = \text{'booked'} \land \neg a_1.\text{is\_deleted} \land a_2.\text{status} = \text{'booked'} \land \neg a_2.\text{is\_deleted}) \implies a_1.\text{id} = a_2.\text{id}$$
  *Diễn giải*: Tại mọi thời điểm, trong toàn bộ database, không bao giờ tồn tại hai bản ghi appointment khác nhau cùng có cùng mốc `starts_at`, cùng có `status = 'booked'` và cùng chưa bị xóa mềm (`is_deleted = False`).

- **INV-02 (Strict Cross-User Ownership Isolation Invariant)**:
  $$\forall a \in \text{Appointments}, \forall u \in \text{Users}: (\text{action}(u, a) \in \{\text{read}, \text{soft\_delete}, \text{restore}\} \land a.\text{owner\_id} \neq u.\text{id}) \implies \text{Result} = \text{AccessDenied (403/404)}$$
  *Diễn giải*: Người dùng không có quyền sở hữu không bao giờ được phép xem, xóa hoặc khôi phục dữ liệu của người dùng khác.

- **INV-03 (Soft Delete Non-destructive Consistency Invariant)**:
  $$\forall a \in \text{Appointments}: a \xrightarrow{\text{soft\_delete}} a' \implies a'.\text{id} = a.\text{id} \land a'.\text{created\_at} = a.\text{created\_at} \land a'.\text{is\_deleted} = \text{True} \land a'.\text{deleted\_at} \neq \text{Null}$$
  *Diễn giải*: Xóa mềm tuyệt đối không xóa cứng bản ghi khỏi database, bảo toàn toàn bộ dữ liệu lịch sử và mốc thời gian tạo lập ban đầu.

---
