# E08 — Deploy đầu tiên lên máy demo qua pipeline (TASK-004, tuần 2)

- **Ngày thực hiện**: 28/10/2026
- **Người phụ trách**: Nguyễn Mai Hoàng Anh (23001824); duyệt deploy: Nguyễn Việt Anh (`anhzxje`)
- **Mốc**: M4 — Release + Deploy
- **Release**: [`v0.2.1`](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/releases/tag/v0.2.1),
  commit `8e9af639565c41af1fe22abc5970e2ffddf1c9a7`
- **Release run**: [40694452038](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40694452038)
- **Deploy run**: [40694848591](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40694848591),
  artifact `deploy-v0.2.1-1`

## 1. Môi trường

| Mục | Giá trị |
| --- | --- |
| Máy demo | VM Multipass `booking-demo`, Ubuntu 24.04.5, 2 vCPU, 3,9 GB RAM, IP `10.97.0.43` |
| Docker | 29.1.3, Compose 2.40.3 (cài bằng `scripts/bootstrap-host.sh`) |
| Runner | `booking-demo`, label `demo`, actions/runner 2.338.2, chạy bằng systemd |
| State dir | `/opt/booking/state` |
| Environment | `demo`: reviewer `anhzxje`, `23001824-HoangAnh`; chặn tự duyệt; chỉ tag `v*` và `main` |

## 2. Dòng thời gian (UTC)

| Thời điểm | Sự kiện |
| --- | --- |
| 13:13:22 | Push tag `v0.2.1` → `release.yml` bắt đầu |
| 13:15:52 | Release xong: test gate pass, push image backend/frontend, tạo GitHub Release kèm `v0.2.1.json` |
| 13:15:55 | `deploy.yml` tự kích hoạt bằng `workflow_run`, chờ duyệt ở environment `demo` |
| 13:23:11 | `anhzxje` duyệt; job bắt đầu trên runner `booking-demo` |
| 13:23:37 – 13:24:40 | `scripts.deploy`: migrate trong image release, pull hai digest, `compose up`, smoke test qua web (62,76 s) |
| 13:24:53 | Job kết thúc, upload artifact |

Lần thử trước với tag `v0.2.0` ([run 40521109514](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40521109514))
fail ở test gate vì `release.yml` thiếu `BOOKING_DATABASE_URL`; đã sửa trong PR #27. Deploy tương
ứng ([run 40521215017](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40521215017)) bị
**skipped**, đúng thiết kế: release không thành công thì không deploy.

## 3. Đối chiếu release với deployment

| Thuộc tính | Manifest `v0.2.1.json` (GitHub Release) | Đang chạy trên máy demo |
| --- | --- | --- |
| Release | `v0.2.1` | `/api/version` → `"release":"v0.2.1"` |
| Commit SHA | `8e9af639565c41af1fe22abc5970e2ffddf1c9a7` | `/api/version` → `"commit_sha":"8e9af639565c41af1fe22abc5970e2ffddf1c9a7"` |
| Backend digest | `sha256:5ee51e7e310780dd586775cacf883b30637f367d2067db8883c71b91ca0158ff` | `booking-backend-1` chạy `ghcr.io/t-ng-d-c-lieu-dong/booking-backend@sha256:5ee51e7e…158ff` |
| Frontend digest | `sha256:8b1ae0895b894760ab0f8339d98b088050422d98b83400814c49693279ca470f` | `booking-web-1` chạy `ghcr.io/t-ng-d-c-lieu-dong/booking-frontend@sha256:8b1ae089…470f` |
| Migration | `20261007_0001` | Chạy bằng service `migrate` từ image backend cùng digest |

`/api/version` được gọi từ máy host qua `http://10.97.0.43/api/version`, tức là qua Nginx giống người
dùng thật. Digest container lấy bằng `docker inspect -f '{{.Config.Image}}'` trên VM.

Kết quả smoke test trong `deploy.log`:

```text
[PASS] (0.10s) readiness_check: Application is ready (HTTP 200 after 0.10s).
[PASS] (0.05s) version_check: Version verified: release='v0.2.1', commit='8e9af639565c41af1fe22abc5970e2ffddf1c9a7'
[PASS] (0.08s) business_flow: Business smoke test passed: slots queried, booking created and cancelled.
Deployment SUCCESSFUL for v0.2.1 in 62.76s!
```

## 4. Kiểm tra cổng mở

| Kiểm tra từ máy host | Kết quả |
| --- | --- |
| `http://10.97.0.43/` (UI) | 200 |
| `http://10.97.0.43/health/ready` | 200, `{"status":"ready"}` từ backend |
| `http://10.97.0.43:8000/health/ready` | Không kết nối được; backend chỉ ở mạng nội bộ |

## 5. Kết luận

**E08 đạt trên máy demo:** tag, commit SHA và digest của cả backend lẫn frontend đang chạy khớp với
manifest của GitHub Release. Deploy đi qua pipeline chuẩn (`release.yml` → `deploy.yml`), có duyệt
của người khác người push tag.

Chưa kiểm chứng trong tài liệu này: rollback qua `rollback.yml` trên máy demo (cần release thứ hai,
thuộc E12 của TASK-005/TASK-007) và observability stack trên máy demo (lịch tuần 4).
