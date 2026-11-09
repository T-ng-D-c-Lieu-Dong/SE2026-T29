# TASK-004 — Container hóa và CI

- Trạng thái: **In Progress**
- Người phụ trách: **Nguyễn Mai Hoàng Anh**
- Mốc: **M3 — Container + CI**
- Phụ thuộc: TASK-002, TASK-003

## Mục tiêu

Đóng gói ứng dụng và tạo kiểm tra tự động để thay đổi lỗi không đi qua pipeline chuẩn.

## Công việc

- Viết Dockerfile cho frontend và backend.
- Tạo Docker Compose cho môi trường local.
- Tạo GitHub Actions chạy lint, backend tests, frontend tests và build checks.
- Dùng PostgreSQL thật cho integration tests trong CI.
- Ghi lại hướng dẫn chạy local và các biến môi trường cần thiết.

## Tiêu chí hoàn thành

- Stack local khởi động được bằng Docker Compose và vượt qua smoke test.
- CI chạy tự động trên pull request.
- Một test cố ý lỗi làm workflow fail và ngăn pipeline chuẩn tiếp tục.
- Kiểm chứng E07 và E13 trong [Evidence](../evidence.md) đạt.

## Đồng bộ trạng thái ngày 25/10/2026

- Đã có Dockerfiles frontend/backend, Compose local, CI backend/frontend, E2E, build và smoke.
- E07/E13 đã có [bằng chứng GitHub/CI](../evidence/2026-10-21-container-ci.md); frontend có
  [kết quả local](../evidence/frontend/2026-10-25-task-003-local.md).
- Người phụ trách xác nhận CI trên commit tích hợp mới nhất trước khi chốt `Done`.

## Đối chiếu tuần 2 ngày 28/10/2026

- C051–C057 và C059 đã merge vào `main` qua PR #26.
- C058 còn thiếu bằng chứng GitHub Environment `demo` có required reviewer thật.
- C060 mới có rehearsal local, chưa có pipeline deploy thật và artifact E08 trên demo host.
- TASK-004 tiếp tục `In Progress`; xem
  [bảng đối chiếu tuần 2](../evidence/2026-10-28-week2-reconciliation.md).
