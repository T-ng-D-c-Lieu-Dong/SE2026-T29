# TASK-002 / VT-118 — Phản hồi validation không lặp lại đầu vào lớn

- Người phụ trách: **Phạm Minh Cương (23001840)** — backend và kiến trúc.
- Ngày kiểm chứng: **25/11/2026**, môi trường phát triển cục bộ.
- Baseline: `6944a36cdb6b3dac06a093053b68706cfebec24b` (`origin/main` khi clone).
- Nhánh: `fix/task-002-validation-errors-23001840`.

## Căn cứ chọn việc

TASK-001/TASK-002 đã Done; VT-118 đã được tích hợp qua PR #37. Trong test VT-118, TC19 vẫn
`xfail(strict=True)` vì handler mặc định của FastAPI trả lại toàn bộ `input` trong lỗi validation.
Đây là việc bảo trì backend có thể kiểm chứng độc lập. Các PR đang mở #30/#40/#41/#42 không
thay handler này hoặc hai file test được sửa trong nhánh này.

## Thay đổi và hợp đồng HTTP

`create_app()` đăng ký handler cho `RequestValidationError`, trả HTTP `422` với danh sách
`detail`. Mỗi phần tử chỉ giữ `type`, `loc`, `msg`; không serialize `input`, `ctx` hoặc request body.
Các thông tin lỗi cần để xác định trường sai vẫn được giữ. Handler áp dụng cho schema body,
JSON không hợp lệ, query và path; các lỗi nghiệp vụ do route phát sinh giữ hợp đồng hiện có.

TC19 bỏ `xfail` và kiểm tra thêm không có booking được lưu hoặc notification được gửi.
Mười ca hồi quy trong `backend/tests/unit/test_validation_errors.py` bao phủ tên lớn, tên dạng
object, tên trắng, thời gian lớn/thiếu timezone, owner lớn, thiếu nhiều field, JSON hỏng, query
ngày lớn và UUID sai. Các ca này không dùng database; nếu request đi tới booking service thì
test thất bại.

## Đo cùng payload trước/sau

Đo bằng `httpx.ASGITransport`, cùng payload `customer_name = "X" * 1_000_000`, thời gian hợp lệ,
header `X-User-Id: validation-test`. So handler mặc định của FastAPI với handler đã đăng ký;
dependency session được thay bằng fixture không kết nối DB vì request phải bị chặn trước service.

| Handler | HTTP | Kích thước response | Các field của lỗi |
| --- | --- | --- | --- |
| Mặc định (baseline) | 422 | 1,000,156 byte | ctx, input, loc, msg, type |
| Sau sửa | 422 | 120 byte | loc, msg, type |

Phép đo này kiểm chứng response validation, không phải benchmark tải hoặc giới hạn request body.

## Kiểm thử và tái lập

Môi trường: Python 3.12.3, FastAPI 0.165.0, Pydantic 2.14.4, SQLAlchemy 2.1.9, pytest 9.2.0,
PostgreSQL 16 (`postgres:16-alpine`), database test riêng `booking_test` trên localhost:55432.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'

# Database test riêng; bảo đảm localhost:55432 chưa được dùng.
docker run --detach --name se2026-t29-validation-23001840-test \
  --publish 127.0.0.1:55432:5432 \
  --env POSTGRES_USER=booking --env POSTGRES_PASSWORD=booking \
  --env POSTGRES_DB=booking_test postgres:16-alpine
# Chờ pg_isready trả thành công trước khi tiếp tục.
docker exec se2026-t29-validation-23001840-test pg_isready -U booking -d booking_test

BOOKING_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test \
  .venv/bin/alembic -c backend/alembic.ini upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test \
  .venv/bin/pytest -q backend/tests --junitxml=reports/backend-tests.xml
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check

# Dọn container test do các lệnh trên tạo sau khi kiểm chứng.
docker rm --force --volumes se2026-t29-validation-23001840-test
```

| Kiểm chứng | Kết quả |
| --- | --- |
| 10 ca hồi quy trên mã cũ, trước khi thêm handler | 10 failed |
| 10 ca hồi quy sau sửa | 10 passed |
| Alembic trên PostgreSQL 16 | Upgrade tới `20261109_0003` thành công |
| Unit backend | 199 passed, 1 xfailed |
| Integration backend với PostgreSQL thật | 60 passed |
| Toàn bộ backend | **259 passed, 1 xfailed** trong 8.22 s |
| Riêng hai file VT-118, tính từ báo cáo JUnit của lần chạy toàn bộ | 32 passed, 1 xfailed |
| Ruff lint / format | Đạt; 152 file đã đúng format |
| `git diff --check` | Đạt |

Lần chạy backend có một cảnh báo deprecation của Starlette TestClient về httpx; không có test
fail hoặc integration test bị bỏ qua. Log và JUnit cục bộ nằm trong `reports/` (được gitignore).
CI của PR sẽ tạo artifact theo workflow hiện có.

## Phạm vi bàn giao và việc còn lại

- TC19 đã được khắc phục; TC18 vẫn là rủi ro đã ghi nhận: notifier chặn event loop vi phạm
  hợp đồng async và không bị `asyncio.timeout` ngắt. Không đổi kênh notifier trong bản sửa này.
- Phần hỗ trợ RCA backend/migration cho TASK-006/TASK-007 vẫn theo checklist diễn tập của nhóm.
  Kết quả cục bộ này không thay cho evidence chạy demo hoặc review của thành viên khác.
- Thay đổi được AI hỗ trợ phân tích, viết patch và chạy kiểm thử theo yêu cầu của người phụ
  trách; không ghi nhận việc sinh viên hoặc nhóm đã review khi chưa có review trên GitHub.
