# Đối chiếu công việc tuần 2 — 28/10/2026

Phạm vi đối chiếu là 50 dòng C051–C100 trong `lich-lam-viec-commit.xlsx`, sau khi pull
`origin/main` tại commit `44c1295` và nhánh PR #28 tại commit `43c634e`.

## Kết quả

| Nhóm | Done | In Progress | Kết luận |
| --- | ---: | ---: | --- |
| TASK-004, C051–C060 | 8 | 2 | Code CD đã merge; còn cấu hình reviewer và deploy thật trên demo |
| TASK-006 backend, C061–C070 | 10 | 0 | Logging, version/fault flag, readiness latency/timeout, pagination và spans đã có test |
| TASK-003 frontend, C071–C080 | 10 | 0 | Hoàn thành gộp tại `daecbc6`, có frontend evidence |
| TASK-007, C081–C090 | 10 | 0 | K6/workflow/smoke/rollback config/runbook đã có; E15 và incident drill vẫn chưa chạy đủ |
| TASK-006 observability, C091–C100 | 10 | 0 | Metrics/logs/outage tests/buckets/exemplars/env docs/E10 local đã có |
| **Tổng** | **48** | **2** | **96% đầu việc tuần 2 có code/evidence** |

## Hai đầu việc chưa hoàn thành

### C058 — Required reviewer cho GitHub Environment `demo`

Workflow đã gắn `environment: demo` tại commit `7c73e26`, nhưng required reviewer là cấu hình
ngoài repository. Admin phải tạo/kiểm tra environment `demo`, thêm reviewer và lưu ảnh/link lần
approval đầu tiên. Vì chưa có bằng chứng này, trạng thái là `In Progress`.

### C060 — Pipeline deploy đầu tiên lên demo host (E08)

Commit `58a5fbc` mới ghi rehearsal local. Evidence nêu rõ chưa có self-hosted runner, GitHub
Release và lần chạy `deploy.yml` thật. Cần chạy pipeline, so `/api/version` với manifest/digest và
lưu link run cùng artifact. Vì vậy trạng thái là `In Progress`.

## Trạng thái task-level

- **TASK-003:** Done.
- **TASK-004:** In Progress vì C058/C060 và PR #27 sửa release migration URL chưa merge.
- **TASK-006:** In Progress dù 20 đầu việc code tuần 2 đã Done; tiêu chí task còn yêu cầu demo
  chung, webhook thật và reliability drill evidence.
- **TASK-007:** In Progress dù 10 đầu việc code tuần 2 đã Done; chưa có phép đo E15 đủ 10 phút,
  incident timeline và rollback drill trên demo host.

## Kiểm tra cục bộ

- Backend unit tests: 125 passed.
- Frontend: lint đạt, 18 tests đạt, production build đạt.
- K6 script tests: 22 passed với Node VM modules.
- Ruff lint/format đạt.
- Workbook sau export: không có lỗi công thức; sheet `Tổng hợp` tính 48/50 Done cho tuần 2.
