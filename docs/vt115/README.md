# VT-115 — Lưu nháp tự động (Nguyễn Mai Hoàng Anh, 23001824)

Change request: thêm cơ chế lưu nháp tự động; dữ liệu mới hơn không được bị bản lưu cũ ghi đè.

- Baseline: `d2dffaff86ab57e878f83d4042c5db288a3da3e7` (main, 2026-10-28)
- Nhánh: `feat/vt115-draft-autosave-23001824`
- API mới: `PUT /api/drafts/{id}` (body: `revision`, `customer_name`, `starts_at`), `GET /api/drafts/{id}`
- Quy tắc: chỉ ghi khi `revision` mới **lớn hơn hẳn** revision đang lưu; ngược lại `409` kèm bản hiện tại.

## Chạy test

```bash
cd backend && docker compose -f compose.test.yaml up -d && cd ..
pip install -e "./backend[dev]"
export TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@localhost:55432/booking_test
pytest backend/tests/integration/test_draft_autosave_api.py -v   # 19 test VT-115
pytest                                                              # toàn bộ suite (161)
pytest backend/tests/integration/test_draft_autosave_api.py --cov=app --cov-report=term-missing
```

Coverage cần `concurrency = greenlet` (đã cấu hình trong `backend/pyproject.toml`); thiếu nó,
coverage báo sai các dòng chạy sau lời gọi DB.

## Kiểm chứng tải (100 người dùng đồng thời, p95 ≤ 3.0 s)

```bash
cd backend && alembic upgrade head && uvicorn app.main:app --port 8000 &
k6 run -e BASE_URL=http://localhost:8000 --summary-export=summary.json loadtest/drafts.js
python loadtest/check_drafts.py summary.json http://localhost:8000
```

## Evidence

`docs/vt115/evidence/`: 01 test fail trước patch · 02 pass sau patch · 03 coverage ·
04–07 mutation M1–M4 · 08 flaky · 09 tải k6 (3 lần chạy).
`docs/vt115/rejected/`: unit test do AI sinh bị loại (bám implementation).

Các nhánh `mutation/vt115-*` chỉ để thí nghiệm, không merge.
