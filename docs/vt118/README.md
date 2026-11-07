# VT-118 — Thông báo `appointment.created` không làm hỏng giao dịch đặt lịch

Bài tập cá nhân 3 · Phạm Minh Cương (23001840) · Nhóm SE2026-T29 · APP-03 Production Readiness Lab

- Nhánh: `feat/vt118-booking-notification-23001840` (không merge khi nhóm chưa review)
- Baseline: `5c8efc21e2a4eaf81d68325bc832098ffe5bf234` (`main`)
- Spec, invariant, review AI plan: [01-spec-plan-review.md](01-spec-plan-review.md) · plan gốc của agent: [ai-plan-v1.md](ai-plan-v1.md)
- Test strategy, bảng test case, traceability, AI usage log: [02-test-strategy-traceability.md](02-test-strategy-traceability.md)

## Thay đổi

`POST /api/appointments` thông báo cho kênh notifier **sau khi** booking đã commit và connection đã trả về pool.
Kênh bị giới hạn bằng `BOOKING_NOTIFICATION_TIMEOUT_SECONDS` (mặc định 0.5 s, cho phép (0, 5]); mọi
`Exception`/timeout trở thành field `notification_status` = `sent` | `failed` | `timeout`, không bao giờ thành 5xx.

| File | Vai trò |
| --- | --- |
| `backend/app/services/notifications.py` | event, `BookingNotifier` protocol, `LoggingBookingNotifier`, `notify_appointment_created` |
| `backend/app/services/booking.py` | `refresh → commit` trong `create()`, `create_and_notify()` |
| `backend/app/api/appointments.py` | dependency `get_booking_notifier`, mapping `NotificationOutcome → notification_status` |
| `backend/app/schemas/appointment.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/.env.example` | response model, setting, wiring + JSON logger |
| `backend/tests/unit/test_booking_notifications.py` | TC01–TC07, TC17, TC18 (xfail), TC20, TC21 |
| `backend/tests/integration/test_appointment_notifications.py` | TC08–TC16, TC19 (xfail), TC22 |

## Chạy test

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && cd ..
docker compose -f backend/compose.test.yaml up -d          # PostgreSQL test ở 127.0.0.1:55432
export TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test

pytest -v backend/tests/unit/test_booking_notifications.py backend/tests/integration/test_appointment_notifications.py
pytest -q backend/tests                                        # toàn bộ: 196 passed, 2 xfailed
ruff check . && ruff format --check .
```

Kết quả mong đợi của file VT-118: `31 passed, 2 xfailed`. Hai xfail (`strict=True`) là residual risk có chủ đích:
TC18 (notifier chặn event loop không bị timeout cắt) và TC19 (422 lặp lại toàn bộ input 1 MB).

## Mutation, coverage, flaky, tải

```bash
docs/vt118/mutations/run_mutations.sh          # 7 mutant "đổi mapping response field"; tự khôi phục backend/app
pytest -q --cov --cov-config=docs/vt118/coveragerc --cov-report=term-missing backend/tests
pip install pytest-randomly && pytest -q -p randomly --randomly-seed=118 backend/tests

# Tải 60 tác vụ đồng thời (cần DB tên *_test, ví dụ booking_load_test):
createdb -h 127.0.0.1 -p 55432 -U booking booking_load_test   # hoặc tạo bằng psql
LABEL=after loadtest/vt118/run_all.sh
git worktree add ../wt-baseline 5c8efc21e2a4eaf81d68325bc832098ffe5bf234   # để đo baseline
BACKEND_DIR=../wt-baseline/backend LABEL=baseline SCENARIOS="default:valid" loadtest/vt118/run_all.sh
```

Mutant không bao giờ được commit lên nhánh nộp bài: M1 được chạy trên nhánh tạm `tmp/vt118-mutation-m1-23001840`
(chỉ local), các mutant còn lại được `git apply` rồi khôi phục bởi script.

## Evidence (`docs/vt118/evidence/`)

| File | Nội dung |
| --- | --- |
| `00-baseline.log` | baseline trước khi sửa: 165 passed |
| `01-plan-review-experiments.log`, `02-oversized-422-echo.log` | thí nghiệm dùng để review AI plan và risk đầu vào lớn |
| `03-red-1-import-error.log` | test-first, đỏ **sai lý do** (ImportError), không tính |
| `04-red-2-assertions.log` | đỏ **đúng lý do** sau khi có stub interface: 22 failed, 6 guard pass |
| `05-green-ai-patch.log` | patch AI: 193 passed, 2 xfailed |
| `06-red-3-review-findings.log`, `07-green-after-review.log` | 2 lỗi tìm khi review patch AI (F1, F2): đỏ → sửa → 195 passed |
| `08`–`10` | mutation: nhánh tạm M1; run 1 (M5 sống sót); run 2 sau TC22 (6/7 killed, M6 tương đương) |
| `11-coverage.log`, `12-flaky.log` | coverage line+branch; 30 lần lặp, 10 thứ tự ngẫu nhiên, 10 lần dưới tải CPU |
| `13-final-fresh-clone.log` | chạy lại toàn bộ từ clone mới + venv mới: 196 passed, 2 xfailed, ruff sạch |
| `load/SUMMARY.md` + `load/*.json` | 60 tác vụ đồng thời: baseline, sau patch, biến thể thứ tự của AI plan |
