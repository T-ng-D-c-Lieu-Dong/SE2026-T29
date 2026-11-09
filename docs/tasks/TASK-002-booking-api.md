# TASK-002 — Xây dựng Booking API

- Trạng thái: **Done**
- Người phụ trách: **Phạm Minh Cương (23001840)**
- Mốc: **M1 — Booking API**
- Phụ thuộc: TASK-001

## Mục tiêu

Xây dựng FastAPI và PostgreSQL cho luồng xem slot, tạo, xem và hủy booking.

## Công việc

- Tạo cấu trúc backend, cấu hình và kết nối PostgreSQL.
- Tạo migration cho bảng `appointments`, constraints và partial unique index.
- Cài đặt health, version, slots và appointments endpoints.
- Tách API, service, repository, model và domain errors theo module view.
- Viết unit tests và integration tests với PostgreSQL thật.

## Tiêu chí hoàn thành

- Các API chính trả đúng status và dữ liệu theo architecture context.
- Hai request đồng thời vào cùng slot cho kết quả một `201`, một `409`.
- Hủy có tính idempotent, giữ lịch sử và cho phép đặt lại slot.
- Các kiểm chứng E01–E05 trong [Evidence](../evidence.md) đạt.

## Kết quả

- Mã nguồn: commit `e0426ba`.
- Migration Alembic chạy thành công trên PostgreSQL 16.
- Ruff lint/format đạt; 21 unit và integration tests pass.
- Chi tiết: [Booking API test result](../evidence/2026-10-07-booking-api.md).

## Bàn giao bổ sung ngày 25/10/2026

- Fault injection có tỷ lệ, thời hạn và mode `error`/`latency`, chạy trước thao tác ghi DB.
- Request log JSON, trace correlation, spans `booking.create`/`booking.cancel` và metric conflict.
- Code bổ sung đã vào `main` qua [PR #14](https://github.com/CuongMotNang/SE2026-T29/pull/14).
- Review kiến trúc và migration hiện tại: [Architecture review](../evidence/2026-10-25-architecture-review.md).
- Tiếp tục phối hợp TASK-006/TASK-007 khi chạy demo; phần triển khai backend của Cương đã bàn giao.
