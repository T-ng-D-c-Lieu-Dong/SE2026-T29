# Tổng hợp Release Manifests và Lịch sử GitHub Actions Workflow Runs

Tài liệu nghiệm thu bằng chứng **E08**, **E12** và phục vụ quản lý truy vết phát hành trong khuôn khổ mốc **M4 (TASK-005)** và **M6 (TASK-007)**.

---

## 1. Danh mục Release Manifests

Tất cả các phiên bản triển khai trên hệ thống đều được định danh thông qua tệp Release Manifest chuẩn định dạng JSON, lưu trữ commit SHA, schema migration revision và digest SHA256 bất biến của từng container image:

| Phiên bản | Tệp Manifest | Commit SHA | Migration Revision | Mục đích & Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **v0.1.0** | [`docs/releases/v0.1.0.json`](../releases/v0.1.0.json) | `e0426ba6...` | `20261007_0001` | Bản phát hành khởi tạo API và hạ tầng cơ sở (M1/M4) |
| **v0.2.0-drill** | [`docs/releases/v0.2.0-drill.json`](../releases/v0.2.0-drill.json) | `d2dffaf0...` | `20261007_0001` | Phiên bản tiêm lỗi chủ đích (`fault.mode: error`, 20% lỗi) phục vụ diễn tập |
| **v0.2.1** | [`docs/releases/v0.2.1.json`](../releases/v0.2.1.json) | `8e9af639...` | `20261007_0001` | Phiên bản ổn định triển khai trên Demo Host, đích khôi phục của Rollback |

---

## 2. Liên kết GitHub Actions Workflow Runs

Quy trình CI/CD và diễn tập sự cố được quản lý tự động thông qua các workflow GitHub Actions:

### 2.1. Continuous Integration (`ci.yml`)
* **Mục tiêu:** Chạy lint, unit tests, integration tests và Docker build kiểm tra trên mọi Pull Request.
* **Các run tiêu biểu:**
  - [Run 40218931201](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40218931201) — Pass 100% test gate cho TASK-004.
  - [Run 40220194812](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40220194812) — Chặn thành công PR lỗi cố ý (Nghiệm thu E07).

### 2.2. Release Automation (`release.yml`)
* **Mục tiêu:** Kích hoạt khi gắn tag phiên bản `v*`, xác thực test gate, build image multi-arch, push lên GitHub Container Registry (GHCR) kèm immutable digest và tạo GitHub Release đính kèm release manifest.
* **Các run tiêu biểu:**
  - [Run 40694452038](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40694452038) — Release `v0.2.1`, xuất bản artifact manifest `v0.2.1.json`.

### 2.3. Automated Deployment (`deploy.yml`)
* **Mục tiêu:** Triển khai phiên bản đã release lên môi trường Demo Host (`booking-demo`) thông qua SSH runner an toàn, yêu cầu phê duyệt từ nhóm phụ trách.
* **Các run tiêu biểu:**
  - [Run 40694848591](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/40694848591) — Deploy thành công `v0.2.1` lên Demo Host (62,76s), hoàn thành nghiệm thu E08.

### 2.4. Emergency Rollback (`rollback.yml`)
* **Mục tiêu:** Khôi phục khẩn cấp về release manifest trước đó khi có sự cố, hỗ trợ kích hoạt thủ công (`workflow_dispatch`) và tự động qua Webhook Alertmanager (`repository_dispatch`).
* **Các run tiêu biểu:**
  - [Run 41029481920](https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/actions/runs/41029481920) — Rollback khẩn cấp từ `v0.2.0-drill` về `v0.2.1`, hoàn thành trong 39,2 giây (Nghiệm thu E12).
