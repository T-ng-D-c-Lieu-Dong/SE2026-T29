# BT3 VT-116 — Nguyễn Việt Anh, 23001827

APP-03 / SE2026-T29. Branch: `bt3/23001827-vt116-soft-delete-restore`.
Baseline: `8fe9de89b719bde237a118e18a671db1d3dfd6cd`.

**PDF và LaTeX nằm ngoài repository**, ở thư mục workspace cha, theo yêu cầu sinh viên. Nộp PDF riêng trên Classroom. Test matrix, traceability và AI Usage Log nằm trong báo cáo; không lưu thêm Markdown trùng lặp ở đây.

Cấu trúc gọn:

- `README.md`: cách chạy và giới hạn chính.
- `evidence/planning/`: audit/plan trước code, giữ để chứng minh assumptions review.
- `evidence/historical/`: nguyên bản RED/GREEN/mutation cũ.
- `evidence/final/`: kết quả mới, coverage, tải cùng run ID, PDF QA và `acceptance.md`.

## Chạy lại (từ root repository)

Python >=3.12; lần chạy ghi nhận dùng3.14.4. Compose thật là `backend/compose.test.yaml`, user/password `booking:booking`. Đợt sửa dùng container riêng trên55433, không dùng database nhóm55432:

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
# Migration drill requires a fresh database; run it BEFORE pytest/load.
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

Wait for pg_isready to succeed. If that container name already exists, inspect it before reuse; do not delete an unfamiliar container. Do not run tests and load concurrently on the same test database. On older Python, use coverage's default core if sysmon is unavailable.

Targeted suite: `backend/tests/unit/test_soft_delete_restore.py`, `backend/tests/integration/test_soft_delete_restore_api.py`, `backend/tests/integration/test_vt116_security_transitions.py` (33 items).

One mutation: on a temporary branch/worktree, invert only `if owner != caller_id:` inside `BookingService.soft_delete` to `if owner == caller_id:` after the historical-owner guard. Run those three files. Recorded temporary commit `1b707ea`:12 FAIL/21 PASS, KILLED. Never mutate/merge that condition into the submitted branch; no general mutation percentage is claimed.

For paired load consistency, run:

```bash
backend/.venv/bin/python scripts/verify_vt116_performance_evidence.py \
  docs/bt3-vt116/evidence/final/performance-20261109T063500Z-038fb4c8.json
```

## Verified results and limitations

- Full suite: **117 PASS / 0 FAIL / 0 SKIP**, one upstream deprecation warning (`evidence/final/18-final-regression.log`).
- Statement coverage808/859 (94.06%); branches166/200 (83.00%). Former exit139 cause is NOT VERIFIED; final sysmon measurement succeeds.
- Three timezone/order runs:33 PASS each. Selected state transitions, including past restore and cancelled lifecycle, have executable checks.
- Load run `20261109T063500Z-038fb4c8`:200/200 lifecycles,600 requests,0 errors,cap40,observed peak lifecycle/HTTP40/40,p95 **420.11ms**. ASGITransport runs in-process with real PostgreSQL; no production/network capacity claim. Latency excludes semaphore queue time and warmup. Paired JSON/log include raw samples.
- Old unpaired performance values482.70/602.2ms are not final evidence; original artifacts remain recoverable from commit58ad4e4.

All `/api/appointments` routes are private and require identity; missing/blank/oversized/reserved callers get401. List filters owner; cross-user detail404,writes403. Create uses caller only; conflicting body owner422. `customer_name` never authenticates ownership. Public slots/health/version expose no patient records.

**OPEN RISK:** `X-User-Id` is only an upstream assertion. Forged valid owner headers still work when calling the backend directly; characterization tests reproduce that limitation. Trusted ingress/IdP must strip client headers, validate tokens, inject identity and deny direct backend access; that integration is not implemented.

Migration0003 sets `owner_access_enabled=false` for all historical rows, including old name owners. Known names/UUIDs cannot enable access. Rows still reserve active slots; verified administrative reassignment is required, without bulk-enabling or deriving owners from names. New ORM bookings are enabled for upstream-asserted ownership, not authenticated identity. Frontend/smoke/persistence callers omitting identity now get401 and need trusted ingress; hardcoded browser headers are not a security fix.

**Local artifacts: READY FOR STUDENT REVIEW. GitHub push: BLOCKED by automatic approval review; remote branch not yet created.** No merge/force-push/history rewrite. Full acceptance table and remaining action: [`evidence/final/acceptance.md`](evidence/final/acceptance.md). No student reflection, experience or academic commitment is signed by AI.
