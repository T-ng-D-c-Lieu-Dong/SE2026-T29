# Tasks — Kế hoạch triển khai

Các task dưới đây chuyển các mốc M0–M6 trong [Evidence](../evidence.md) thành công việc có thể phân công và kiểm chứng.

## Backlog

| ID | Task | Mốc | Trạng thái | Người phụ trách | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| TASK-001 | [Xác nhận kiến trúc](TASK-001-confirm-architecture.md) | M0 | Done | Phạm Minh Cương (23001840) | Không |
| TASK-002 | [Xây dựng Booking API](TASK-002-booking-api.md) | M1 | Done | Phạm Minh Cương (23001840) | TASK-001 |
| TASK-003 | [Xây dựng React UI](TASK-003-react-ui.md) | M2 | Done | Lê Văn Cường | TASK-002 |
| TASK-004 | [Container hóa và CI](TASK-004-container-ci.md) | M3 | In Progress | Nguyễn Mai Hoàng Anh | TASK-002, TASK-003 |
| TASK-005 | [Release, deploy và rollback](TASK-005-release-deploy.md) | M4 | Done | Nguyễn Việt Anh (23001827) | TASK-004 |
| TASK-006 | [Observability và cảnh báo](TASK-006-observability.md) | M5 | In Progress | Vũ Thành Công | TASK-004 |
| TASK-007 | [Reliability demo và evidence](TASK-007-reliability-demo.md) | M6 | In Progress | Nguyễn Việt Anh (23001827) | TASK-005, TASK-006 |

## Quy ước quản lý

- Trạng thái dùng một trong các giá trị: `Todo`, `In Progress`, `In review`, `Blocked`, `Done`.
- Trước khi bắt đầu, điền người phụ trách và đổi trạng thái thành `In Progress`.
- Chỉ chuyển sang `Done` khi toàn bộ tiêu chí hoàn thành đã đạt và evidence tương ứng được lưu.
- Mỗi pull request ghi ID task trong mô tả, ví dụ `TASK-002`.
- Nếu phạm vi hoặc tiêu chí thay đổi, cập nhật task và tài liệu kiến trúc liên quan trong cùng pull request.
