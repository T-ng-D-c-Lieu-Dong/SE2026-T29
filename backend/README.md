# Booking API

FastAPI backend cho dịch vụ đặt lịch. API dùng PostgreSQL để bảo vệ transaction và ngăn hai booking đang hoạt động dùng cùng một slot.

## Yêu cầu

- Python 3.12+
- PostgreSQL 16 hoặc tương thích

## Cài đặt

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]"
```

Trên Linux hoặc macOS, dùng `source .venv/bin/activate` thay cho lệnh kích hoạt trên Windows.

Sao chép `.env.example` thành `.env` hoặc khai báo các biến môi trường tương ứng. Không commit file `.env`.

## Khởi tạo database và chạy API

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API mặc định chạy tại `http://localhost:8000`; OpenAPI tại `/docs`.

`BOOKING_DEFAULT_PAGE_SIZE` đặt số appointment mặc định mỗi trang (1–100, mặc định 20).
Tham số `limit` tường minh vẫn được ưu tiên. Cấu hình được đọc khi khởi động
process và cần restart để thay đổi.

## Chạy tests

Khởi động PostgreSQL test riêng:

```bash
docker compose -f compose.test.yaml up -d
```

Khai báo URL database test rồi chạy:

```bash
set TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@localhost:55432/booking_test
pytest
```

Trên PowerShell, dùng `$env:TEST_DATABASE_URL=...`; trên Linux/macOS, dùng `export TEST_DATABASE_URL=...`.

Database integration test bắt buộc có tên kết thúc bằng `_test`. Test sẽ từ chối chạy nếu URL trỏ tới database khác.

## Fault injection cho reliability drill

Fault injection mặc định tắt và chỉ áp dụng cho thao tác tạo booking, trước khi ghi dữ liệu:

- `BOOKING_FAULT_MODE=off|error|latency`: tắt fault, trả HTTP 500, hoặc tạo độ trễ.
- `BOOKING_FAULT_RATE`: tỷ lệ request bị tác động, từ `0.0` đến `1.0`.
- `BOOKING_FAULT_UNTIL`: thời điểm tự tắt theo ISO 8601 có múi giờ, ví dụ
  `2026-10-26T15:00:00+07:00`. Bắt buộc khi mode là `error` hoặc `latency`;
  chỉ để trống khi fault đang tắt.
- `BOOKING_FAULT_LATENCY_SECONDS`: số giây trễ ở chế độ `latency`, mặc định là `3`.

Ví dụ tạo lỗi cho 25% request trong một khoảng thời gian giới hạn:

```dotenv
BOOKING_FAULT_MODE=error
BOOKING_FAULT_RATE=0.25
BOOKING_FAULT_UNTIL=2026-10-26T15:00:00+07:00
```

Sau thời điểm `BOOKING_FAULT_UNTIL`, fault tự ngừng mà không cần restart ứng dụng. Không dùng
fault injection trong môi trường production ngoài một reliability drill đã được phê duyệt.

## Structured logging và OpenTelemetry

Mỗi HTTP request tạo một log JSON trên stdout với `method`, route template, status,
`duration_ms`, release, commit SHA và trace/span ID khi có. Middleware không đọc hoặc ghi
request body, query string, tên khách hàng hay ID thật trong URL.

OpenTelemetry mặc định tắt. Bật export traces, metrics và logs qua OTLP/gRPC bằng:

```dotenv
BOOKING_TELEMETRY_ENABLED=true
BOOKING_DEPLOYMENT_ENVIRONMENT=demo
BOOKING_OTLP_ENDPOINT=http://otel-collector:4317
```

Ứng dụng instrument FastAPI và SQLAlchemy, tạo span `booking.create`, `booking.cancel`, và
counter `booking_conflicts_total` khi trả HTTP 409. Export dùng batch queue hữu hạn và timeout
ngắn để Collector lỗi không chặn luồng đặt lịch. Các giới hạn có thể chỉnh bằng nhóm biến
`BOOKING_TELEMETRY_*` trong `.env.example`.

Hai file Compose của repository chỉ cấu hình ứng dụng để gửi OTLP, chưa khởi chạy Collector.
Khi bật telemetry, `BOOKING_OTLP_ENDPOINT` phải trỏ tới một Collector bên ngoài mà container
backend truy cập được; tên `otel-collector` chỉ dùng khi Collector đó cùng Docker network.
