# Architecture

Thư mục này mô tả kiến trúc của Production Readiness Lab đã được đối chiếu với mã nguồn ngày
25/10/2026. Phạm Minh Cương (23001840) phụ trách chốt thiết kế trong TASK-001. Những nội dung
chưa được kiểm chứng trên máy demo vẫn được ghi rõ là mục tiêu hoặc công việc còn lại.

## Tài liệu

1. [Architecture context](architecture-context.md) — phạm vi, người dùng, ràng buộc, API và mục tiêu chất lượng.
2. [Module view](module-view.md) — cấu trúc mã nguồn, trách nhiệm và hướng phụ thuộc.
3. [Runtime view](runtime-view.md) — các thành phần khi chạy, luồng request, telemetry, deploy và rollback.
4. [ADR-001](adr/001-use-docker-compose.md) — quyết định Accepted dùng Docker Compose trên một Linux VM.
5. [Kết quả review kiến trúc và migration](../evidence/2026-10-25-architecture-review.md) — phạm vi chốt, đối chiếu code, bằng chứng và việc bàn giao.

## Quy tắc cập nhật

- Cập nhật tài liệu kiến trúc cùng pull request khi code hoặc cấu hình làm thay đổi thiết kế.
- Tạo ADR mới cho quyết định quan trọng; không xóa ADR cũ khi quyết định bị thay thế.
- Dùng trạng thái `Proposed`, `Accepted`, `Deprecated` hoặc `Superseded` cho ADR.
- Liên kết thay đổi với [task](../tasks/README.md) và cập nhật [Evidence](../evidence.md) khi đã có kết quả kiểm chứng.
