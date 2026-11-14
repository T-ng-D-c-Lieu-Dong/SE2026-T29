# VT-117: kiểm thử và tải giả lập

Baseline: 2a4bbc3b246e1f2c9b947a4d8de56489a4b37fc9. Patch: 6d9bf5f.

```powershell
python -m pytest backend/tests/unit/test_page_size_contract.py -q
$env:PYTHONPATH='backend'
python bt3/load_harness.py
```

Harness dùng ASGI cùng process, 120 coroutine, repository giả chờ 10ms. Không suy ra khả năng production. PostgreSQL test: xem backend/README.md; cần Docker daemon và TEST_DATABASE_URL. Logs fail trước patch và mutation ở thư mục gốc.

## PostgreSQL và tải thực cục bộ

Chỉ dùng database test `booking_test` riêng. Harness từ chối seed nếu bảng không rỗng,
tạo hai bản ghi tạm và xóa đúng hai ID khi kết thúc; dùng cổng 18976.

```powershell
docker compose -f backend/compose.test.yaml up -d
$env:TEST_DATABASE_URL='postgresql+asyncpg://booking:booking@localhost:55432/booking_test'
python -m pytest backend/tests/integration/test_appointments_api.py -q
$env:PYTHONPATH='backend'
python bt3/load_postgres.py
python -m coverage run --branch -m pytest backend/tests/unit/test_page_size_contract.py -q
python -m coverage report -m --include='*/app/config.py,*/app/api/appointments.py,*/app/services/booking.py'
```

Một burst 120 request qua HTTP và PostgreSQL cục bộ không đại diện cho sản xuất.
