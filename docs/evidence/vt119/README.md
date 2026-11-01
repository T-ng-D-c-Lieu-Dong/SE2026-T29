# VT-119 — Export API (Lê Văn Cường, 23001842, nhóm SE2026-T29)

Branch: `vt119/export-api-23001842` · Baseline commit: `d2dffaf` (main) · Endpoint:
`GET /api/exports/appointments?from=YYYY-MM-DD&to=YYYY-MM-DD[&include_cancelled=true]`
Header `X-API-Key`; khóa cấu hình qua `BOOKING_EXPORT_API_KEYS=token:role,token:role`
(role `export_staff` = chỉ booked; `export_admin` = thêm cancelled; role khác = 403).

## Chạy test (cần PostgreSQL; tên DB phải kết thúc `_test`)
```bash
cd backend
python -m pip install -e ".[dev]" pytest-cov
docker compose -f compose.test.yaml up -d
export TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@localhost:55432/booking_test
python -m pytest                                   # toàn bộ suite (192 test, gồm 50 test VT-119)
python -m pytest tests/unit/test_export_policy.py \
  tests/integration/test_export_api.py tests/integration/test_export_repository_contract.py
python -m pytest --cov=app --cov-branch --cov-report=term-missing
ruff check . && ruff format --check .
```
## Tái lập evidence
- Red: `git checkout 72377d4 && pytest <3 file test VT-119>` (chỉ có test, chưa có patch).
- Green: `git checkout <HEAD của branch>`.
- Mutation: áp từng mutant trong `docs/evidence/vt119/03..05-*.log` (mô tả diff 1 dòng) trên nhánh tạm,
  chạy `pytest`, rồi `git checkout -- backend`. Không có mutant nào được commit.
- Tải: `python scripts/vt119_export_load.py --seed`, chạy API, rồi
  `python scripts/vt119_export_load.py --users 150 --rounds 5 --target-p95 4.0`.
