# TASK-003 — Xây dựng React UI

- Trạng thái: **Done**
- Người phụ trách: **Lê Văn Cường**
- Mốc: **M2 — UI**
- Phụ thuộc: TASK-002

## Mục tiêu

Cung cấp giao diện để người dùng xem slot, đặt, xem và hủy lịch qua API thật.

## Công việc

- Tạo React project và HTTP client dùng đường dẫn `/api`.
- Xây dựng form đặt lịch và danh sách booking.
- Hiển thị thời gian theo `Asia/Ho_Chi_Minh`.
- Xử lý rõ trạng thái loading, success, empty và error, bao gồm lỗi `409`.
- Viết component tests và end-to-end test cho luồng đặt/hủy.

## Tiêu chí hoàn thành

- UI không tự quyết định uniqueness; kết quả hiển thị dựa trên response API.
- Người dùng thực hiện được luồng tạo, xem và hủy booking.
- E2E chạy qua UI → API → PostgreSQL thành công.
- Kiểm chứng E06 trong [Evidence](../evidence.md) đạt.

## Kết quả kiểm chứng (25/10/2026)

- Frontend lint, format, build, 18 unit/component tests và 8 Playwright E2E tests trên Compose/PostgreSQL đều đạt; xem [bằng chứng kiểm chứng](../evidence/frontend/2026-10-25-task-003-local.md).
