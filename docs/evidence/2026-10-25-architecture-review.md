# TASK-001 — Review kiến trúc và bàn giao backend

- Ngày chốt: **25/10/2026**.
- Người phụ trách: **Phạm Minh Cương — 23001840**, backend và kiến trúc.
- Source đối chiếu: `origin/main` tại `fa8422f189a7946b6de0c494d143b86cdeaf3287`.
- Phạm vi: context, module/runtime views, ADR-001 và review tương thích schema của phần backend.
- Căn cứ quyết định: yêu cầu hoàn tất phần việc của người phụ trách trong TASK-001/TASK-002.
  Đây là bản chốt kỹ thuật được bàn giao qua pull request; không ghi nhận thay một cuộc họp nhóm
  hoặc approval của thành viên khác chưa xảy ra. Review/approval của nhóm lưu tại pull request.

## 1. Các quyết định được giữ cho MVP

| Nội dung | Quyết định | Code hoặc tài liệu đối chiếu |
| --- | --- | --- |
| Nghiệp vụ | Một lịch dùng chung, slot 30 phút, chỉ đặt thời gian tương lai | `backend/app/services/booking.py` |
| Thời gian | API bắt buộc offset, chuẩn hóa UTC; UI dùng `Asia/Ho_Chi_Minh` | `backend/app/schemas/appointment.py`, `frontend/src/time.ts` |
| Đồng thời | Partial unique index bảo vệ một active booking/slot; conflict trả 409 | `backend/app/repositories/appointments.py`, `backend/app/models/appointment.py` |
| Hủy | Giữ bản ghi cancelled, cho phép đặt lại; hủy lặp cùng ID trả 204 | Service và API appointments |
| Quyền truy cập | Dữ liệu giả, lịch dùng chung; chưa có tài khoản và quyền sở hữu booking | [Architecture context](../architecture/architecture-context.md) |
| Cấu trúc | Modular monolith: API → service → repository → PostgreSQL | [Module view](../architecture/module-view.md) |
| Triển khai | Chọn Docker Compose trên một Linux VM cho demo | [ADR-001 Accepted](../architecture/adr/001-use-docker-compose.md) |
| Vận hành | Readiness có timeout; fault mặc định tắt và bắt buộc hạn; export OTel theo batch | `backend/app/api/health.py`, `services/fault_injection.py`, `telemetry/` |

Việc chấp nhận ADR xác nhận cách tổ chức hệ thống. SLO 30 ngày, tải 10 request/giây và rollback
trong 5 phút vẫn là mục tiêu cần kết quả đo, không suy ra từ trạng thái `Accepted`.

## 2. Kết quả đối chiếu module và runtime

- Routes và schemas xử lý hợp đồng HTTP; service thực thi slot/timezone và commit nghiệp vụ;
  repository dùng SQLAlchemy, rollback khi flush lỗi và chỉ ánh xạ unique index active-slot sang
  `SlotAlreadyBooked`. Lỗi DB khác không bị đổi thành conflict 409.
- Frontend gọi `/api` cùng origin qua Nginx; không truy cập DB. Đã có BookingPage, components,
  API client, component tests và Playwright E2E.
- `main.py` nối cấu hình, routes, request logging và telemetry. Service không phụ thuộc FastAPI.
- Log JSON dùng route template; server span bỏ URL/query động. Các bảo đảm này áp dụng cho
  backend logger/instrumentation, không phải mọi access log của Nginx.
- Local Compose có DB → migrate → backend → web với điều kiện health/job hoàn tất. Production
  Compose hiện chỉ có backend/DB. Observability được thêm qua overlay và cấu hình trong
  `deploy/observability/`.
- Release workflow hiện chỉ build/push backend; manifest hỗ trợ frontend tùy chọn nhưng luồng
  phát hành/triển khai frontend chưa hoàn tất. `rollback.yml` còn chạy trên `ubuntu-latest`;
  chưa có `deploy.yml` hướng vào máy demo có manifest/state lưu bền vững.
- Deploy/rollback scripts phục hồi backend digest, release và SHA. Fault nằm ngoài image cần
  tắt bằng cấu hình/recreate hoặc chờ hết hạn; chưa có tự động snapshot toàn bộ fault config.

Các khác biệt giữa local, production hiện tại và đích demo đã được ghi lại trong
[Runtime view](../architecture/runtime-view.md). Không cam kết HA hoặc zero-downtime.

## 3. Review migration và rollback

Repository hiện chỉ có revision **`20261007_0001`**, tạo bảng `appointments` với UUID,
`customer_name VARCHAR(100)`, timestamp có timezone, trạng thái booked/cancelled, index theo
thời gian và partial unique index `uq_appointments_active_starts_at`.

- Model và migration thống nhất các cột, kiểu, nullability, server defaults và predicate
  `status = 'booked'`. `cancelled_at` nullable; các cột còn lại bắt buộc.
- Phần fault injection, JSON logging và OpenTelemetry tại commit `3fa1b32` không sửa schema.
  Không cần thêm migration hoặc downgrade để rollback phần backend này.
- Migration đầu tiên có `downgrade()` xóa bảng, nên không dùng downgrade đó để khôi phục ứng
  dụng trong drill có dữ liệu. Giữ volume và schema khi đổi image.
- Các migration sau phải theo [migration policy](../releases/migration-policy.md): expand trước,
  contract sau cửa sổ rollback; review tác động của constraint/index lên code phiên bản trước.

Test `test_e14_schema_backward_compatibility_during_rollback_window` hiện chạy code và model
schema hiện tại. Nó không chạy hai image khác release, nên chưa tự chứng minh tương thích của
một migration tương lai. Khi schema thay đổi, phải ghi evidence với image rollback thật trên DB
đã upgrade; đây là kiểm chứng thuộc release/drill của nhóm.

## 4. Kiểm chứng ngày 25/10/2026

Các lệnh chạy từ repo root, trừ Alembic và pytest chạy trong `backend/`:

| Kiểm tra | Kết quả |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m ruff check .` | Đạt |
| `backend/.venv/Scripts/python.exe -m ruff format --check .` | Đạt, 91 file Python |
| `python -m pytest tests/unit -q -p no:cacheprovider --basetemp F:\CNPM\.test-tmp-architecture\unit` | **88 passed**, một warning deprecation của Starlette/httpx |
| `python -m alembic heads` | Một head: `20261007_0001` |
| `python -m alembic upgrade head --sql` | Sinh DDL PostgreSQL thành công, đúng schema/index; không ghi DB |
| `docker compose -f deploy/compose.yaml config --quiet` | Đạt |
| `docker compose -f deploy/compose.production.yaml config --quiet` | Đạt |
| Local và production Compose ghép `deploy/compose.observability.yaml`, `config --quiet` | Cả hai đạt |

Lần chạy pytest đầu dùng Temp mặc định bị lỗi quyền `WinError 5` trước một số test; chạy lại với
basetemp trong workspace đạt toàn bộ 88 tests. Lần review này thay đổi tài liệu, không chạy lại
integration DB/E2E/drill hoặc coi `compose config` là bằng chứng stack đã khởi động.

Kết quả trước đó để truy vết: [API E01–E05](2026-10-07-booking-api.md),
[backend fault/log/OTel](2026-10-21-backend-observability.md),
[UI/E2E E06](frontend/2026-10-25-task-003-local.md),
[E09 correlation](observability/2026-10-22-local-e09.md),
[E10 Collector outage](observability/2026-10-22-local-e10.md).

## 5. Bàn giao và trách nhiệm còn lại

| Phần | Trạng thái / người tiếp tục |
| --- | --- |
| TASK-001: context, views, ADR và review migration | Cương đã chốt và bàn giao trong thay đổi này |
| TASK-002: API, fault có hạn, log JSON, spans/metric | Cương đã bàn giao; code bổ sung đã merge qua PR #14 |
| Review migration mới khi có thay đổi DB | Cương phối hợp người làm release trước mỗi lần deploy |
| Máy demo, production web, workflow deploy/rollback và release frontend | Phối hợp Hoàng Anh / Việt Anh theo kế hoạch; chưa coi là hoàn tất |
| Discord thật, ảnh Grafana, drill observability máy demo | Công / Hoàng Anh; E11 local chưa xác nhận thông báo thật |
| E15, rollback toàn trình và incident report | TASK-007; nhóm xác nhận owner trước khi chạy |

E11 local ngày 25/10 đã có firing/resolved trong Prometheus và Alertmanager; xem
[kết quả và giới hạn](observability/2026-10-25-local-e11.md). Các phần demo còn lại không được
đánh dấu `Done` chỉ vì TASK-001 hoặc backend đã hoàn thành.
