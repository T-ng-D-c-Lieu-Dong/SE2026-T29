# BT3 VT-116 — Nguyễn Việt Anh, 23001827

Dự án APP-03 / SE2026-T29. Branch: `bt3/23001827-vt116-soft-delete-restore`.
Baseline: `8fe9de89b719bde237a118e18a671db1d3dfd6cd`.

Thư mục này chỉ chứa kế hoạch kỹ thuật và evidence để đối chiếu code/test. Báo cáo cá nhân nộp riêng.

- `evidence/planning/`: khảo sát repository, kế hoạch trước code và review assumptions.
- `evidence/historical/`: log RED/GREEN và mutation của phần triển khai ban đầu, giữ nguyên nội dung.
- `evidence/final/`: RED của bản vá bảo mật, migration, regression, coverage, mutation, flaky checks và tải cuối.

## Chạy lại từ root repository

Python >=3.12; môi trường ghi nhận dùng Python 3.14.4. Compose của dự án là `backend/compose.test.yaml`, user/password `booking:booking`. Evidence đợt sửa dùng PostgreSQL riêng trên cổng 55433, không dùng database nhóm trên 55432.

```bash
docker run -d --name vt116-final-postgres --label purpose=vt116-final-isolated \
  -e POSTGRES_DB=vt116_final_test -e POSTGRES_USER=booking -e POSTGRES_PASSWORD=booking \
  -p 127.0.0.1:55433:5432 --tmpfs /var/lib/postgresql postgres:18-alpine
docker exec vt116-final-postgres pg_isready -U booking -d vt116_final_test
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[dev]'
export TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55433/vt116_final_test
export BOOKING_DATABASE_URL="$TEST_DATABASE_URL"
export PYTHONPATH=.:backend
# Migration drill cần DB mới; chạy trước pytest/load.
backend/.venv/bin/python scripts/verify_vt116_migration.py
backend/.venv/bin/pytest backend/tests -v -p no:cacheprovider
COVERAGE_CORE=sysmon backend/.venv/bin/python -m coverage run --branch \
  --source=backend/app -m pytest backend/tests -q -p no:cacheprovider
backend/.venv/bin/python -m coverage report -m
backend/.venv/bin/python scripts/verify_vt116_flaky.py
backend/.venv/bin/python scripts/loadtest_vt116.py --output-dir /tmp/vt116-load
backend/.venv/bin/ruff check .
backend/.venv/bin/ruff format --check .
```

Chờ `pg_isready` thành công. Nếu tên container đã tồn tại, kiểm tra trước khi dùng; không xóa container không rõ nguồn gốc. Không chạy pytest và load đồng thời trên cùng DB. Với Python không hỗ trợ sysmon, dùng coverage core mặc định.

## Đối chiếu kết quả

Các đường dẫn trong bảng thuộc `evidence/final/`.

| Nội dung | Evidence | Kết quả ghi nhận |
|---|---|---|
| RED bản vá identity | `01-security-red.log`, `03-historical-owner-red.log` | 10 fail/5 pass trước patch; test dữ liệu cũ phát hiện model thiếu access flag |
| Migration có dữ liệu cũ | `08-migration.log` | Baseline → 0002 → 0003; dữ liệu được giữ và mặc định khóa quyền truy cập |
| Full regression | `09-full-pytest.log`, `18-final-regression.log` | 117 PASS, 0 FAIL, 0 SKIP; một warning deprecation của thư viện |
| Line/branch coverage | `10-coverage-sysmon.log`, `11-coverage-report.log`, `coverage.json` | 808/859 statements (94.06%); 166/200 branches (83.00%) |
| Mutation ownership | `13-mutation.log` | Một mutation bị phát hiện: 12 fail/21 pass |
| Flaky risks time/order | `14-flaky-review.log` | 33 test pass trong cả 3 lần chạy với timezone/thứ tự khác nhau |
| Load và đối chiếu metric | Cặp `performance-20261109T063500Z-038fb4c8.json`/`.log`, `15-performance-consistency.log` | 200/200 lifecycle, 600 request, 0 lỗi, peak40, p95 420.11ms |

Mỗi log chạy có command, môi trường và tested SHA. Backend/harness được đo tại `c3421e2`; regression cuối tại `7f5f56f`. Các commit sau đó cập nhật tài liệu, không đổi hành vi backend.

Suite VT-116 gồm 33 items trong:

- `backend/tests/unit/test_soft_delete_restore.py`
- `backend/tests/integration/test_soft_delete_restore_api.py`
- `backend/tests/integration/test_vt116_security_transitions.py`

Mutation được chạy trên branch tạm, commit `1b707ea`: chỉ đảo `if owner != caller_id:` thành `if owner == caller_id:` trong `BookingService.soft_delete`, sau historical-owner guard. Để tái lập, tạo branch/worktree tạm, đảo đúng occurrence đó và chạy ba file test trên. Không đưa mutation vào branch nộp; không suy ra tỷ lệ mutation coverage tổng quát từ một mutation.

Đối chiếu samples với log tải:

```bash
backend/.venv/bin/python scripts/verify_vt116_performance_evidence.py \
  docs/bt3-vt116/evidence/final/performance-20261109T063500Z-038fb4c8.json
```

## API contract và giới hạn kết luận

Mọi route `/api/appointments` bắt buộc identity. Thiếu/rỗng/quá dài/reserved caller trả401; list lọc owner; detail chéo owner trả404; ghi chéo owner trả403. Create dùng caller, không dùng `customer_name` làm owner; body owner khác caller trả422. Slots/health/version là public và không trả thông tin bệnh nhân.

`X-User-Id` vẫn chỉ là identity assertion: giả header hợp lệ có thể truy cập khi gọi backend trực tiếp. Các test spoofing ghi nhận giới hạn này, không chứng minh đã chặn giả mạo. Trusted ingress/IdP phải xác thực, loại header do client tự gửi và chặn truy cập trực tiếp; phần đó chưa triển khai.

Migration0003 đặt `owner_access_enabled=false` cho mọi bản ghi cũ, kể cả owner từng suy từ tên. Client không thể tự mở quyền bằng tên/UUID. Dữ liệu cũ vẫn giữ slot active; việc gán lại owner cần xác minh độc lập. Caller frontend/smoke/persistence trước đây không gửi identity nay nhận401 và cần tích hợp trusted ingress.

Tải dùng ASGITransport trong cùng tiến trình với PostgreSQL thật. Latency không gồm thời gian chờ semaphore hoặc warmup; chưa phản ánh network/gateway hay capacity production. Peak40 là quan sát cực đại, không phải luôn có40 request liên tục. Các lần chạy flaky chỉ là quan sát hữu hạn; tests đồng thời chưa ép mọi DB interleaving bằng barrier.
