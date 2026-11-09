# CD lên máy demo — Diễn tập cục bộ (TASK-004, tuần 2)

- **Ngày thực hiện**: 27/10/2026
- **Người phụ trách**: Nguyễn Mai Hoàng Anh (23001824)
- **Mốc**: M4 — Release + Deploy (phần đưa lên máy demo)
- **Nhánh**: `feat/task-004-cd-demo-host`, commit `60d2552` (image), scripts và compose ở `6919bd0`
- **Môi trường**: Linux 7.0, Docker 29.6.2, Compose 5.3.1, registry `registry:2` chạy local

**Phạm vi:** đây là diễn tập đường deploy production (`scripts/deploy.py`, `scripts/rollback.py`,
`deploy/compose.production.yaml`) trên máy cá nhân. Chưa phải bằng chứng E08 trên máy demo: chưa có
self-hosted runner, chưa có GitHub Release và workflow `deploy.yml` chưa chạy lần nào.

## 1. Cách chạy

1. Build image backend và frontend, push vào registry local để có digest thật.
2. Tạo manifest `v0.9.0`, `v0.9.1` bằng `python -m scripts.release_manifest create` với cả
   `--backend-digest` và `--frontend-digest`.
3. Deploy `v0.9.0`, seed một booking, deploy `v0.9.1`, rollback về manifest trước, rồi verify booking.
   Mọi lệnh dùng `--state-dir` riêng và `--base-url http://localhost:18180` (cổng web).

## 2. Kết quả

| Bước | Kết quả | Thời gian |
| --- | --- | --- |
| Deploy `v0.9.0` (DB mới, chạy `migrate` từ image release) | Thành công, smoke test pass qua web | 16,52 s |
| Seed booking | `7cfd108c-7ebc-4e2b-8c31-8dd875ee4965` | — |
| Deploy `v0.9.1` | Thành công; `/api/version` trả `v0.9.1` | 11,92 s |
| Rollback về `previous-manifest.json` | Thành công; `/api/version` trả `v0.9.0`; `[SLO MET]` | 8,03 s |
| Verify booking sau rollback | `[PASS] ... survived recreate` | — |

`history.json` trong state dir ghi đủ ba thao tác:

```text
deploy v0.9.0 success 16.52
deploy v0.9.1 success 11.92
rollback v0.9.0 success 8.03
```

Kiểm tra cổng mở sau deploy (`docker compose ps`):

```text
backend localhost:5005/booking-backend@sha256:78aff098…  [8000/tcp, không publish]
db      postgres:16-alpine                               [5432/tcp, không publish]
web     localhost:5005/booking-frontend@sha256:89894341… [0.0.0.0:18180->80/tcp]
```

Gọi `http://localhost:8000/health/ready` từ host không kết nối được, đúng thiết kế chỉ mở cổng web.

## 3. Lỗi phát hiện và đã sửa trong nhánh

| Lỗi | Hậu quả nếu không sửa | Commit |
| --- | --- | --- |
| `deploy.py` chạy `alembic` trên host | Deploy fail ở bước migration vì máy demo không có dependency backend và DB không mở port | `7b3f72d` |
| Nginx resolve `backend` một lần lúc khởi động | Sau khi deploy recreate backend, web trả 502 (đã tái hiện bằng Compose) | `60d2552` |
| Nginx không proxy `/health/` | `/health/ready` qua web trả `index.html` với HTTP 200, smoke test pass giả | `60d2552` |
| `release.yml` dùng tên image có chữ hoa | GHCR từ chối push, tag release không tạo được manifest | `d8e723e` |

## 4. Còn thiếu cho E08 trên máy demo

- Admin repository đăng ký runner `booking-demo` (label `demo`) và tạo environment `demo` theo
  [demo-host.md](../devops/demo-host.md).
- Merge nhánh vào `main`, push tag release đầu tiên, duyệt job deploy.
- So khớp `/api/version` trên máy demo với manifest và digest đang chạy, lưu link run và artifact
  `deploy-<tag>-<attempt>` vào tài liệu này hoặc một evidence mới.
