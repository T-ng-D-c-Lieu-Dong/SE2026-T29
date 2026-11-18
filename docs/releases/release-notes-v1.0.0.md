# Release Notes — Version v1.0.0 (Production Readiness Lab)

- **Phiên bản:** `v1.0.0`
- **Ngày phát hành:** 27/11/2026
- **Nhóm thực hiện:** SE2026-T29
- **Manifest:** [`docs/releases/v1.0.0.json`](v1.0.0.json)

---

## 1. Giới thiệu tổng quan (Overview)

Phiên bản **v1.0.0** đánh dấu cột mốc hoàn thành toàn diện đồ án **Production Readiness Lab (APP-03)** của nhóm **SE2026-T29**. Toàn bộ các mốc phát triển từ **M0 đến M6** và 16 cam kết thiết kế **E01–E16** đã được nghiệm thu đầy đủ trên môi trường máy chủ Demo Host thực tế.

Hệ thống cung cấp giải pháp đặt lịch hẹn trực tuyến hoàn chỉnh với giao diện React thân thiện, backend FastAPI hiệu năng cao, cơ chế phòng vệ chống đặt trùng lịch mức cơ sở dữ liệu, pipeline CI/CD khép kín, stack quan sát đa tầng và khả năng tự động khôi phục sự cố dưới 5 phút.

---

## 2. Các tính năng & Cột mốc nổi bật (Key Milestones & Features)

### 2.1. Nghiệp vụ & Dữ liệu (M1, M2 — TASK-002, TASK-003)
* **Booking API:** Các endpoint RESTful `/api/appointments`, `/api/slots`, `/api/health`, `/api/version` xây dựng trên nền FastAPI và SQLAlchemy 2.0.
* **Chống trùng slot:** Ứng dụng PostgreSQL partial unique index `uq_appointments_active_starts_at` và isolation level chống xung đột đồng thời, giải quyết triệt để lỗi double-booking.
* **React Web UI:** Giao diện đặt lịch responsive, hiển thị slot trực quan, tích hợp xử lý lỗi thân thiện và cập nhật trạng thái tức thời.

### 2.2. Đóng gói & Tự động hóa Pipeline (M3, M4 — TASK-004, TASK-005)
* **Container hóa tối ưu:** Dockerfile multi-stage cho Backend và Frontend Nginx, giảm kích thước image và nâng cao tính bảo mật.
* **Release Manifest bất biến:** Mọi phiên bản phát hành được định danh bằng SHA256 image digest, commit SHA và schema migration revision, lưu trữ tại `docs/releases/`.
* **Quy trình Deploy & Rollback tự động:** Triển khai qua Docker Compose với khóa bảo vệ chống tranh chấp (`deploy_lock.py`), kiểm tra sức khỏe tự động (`smoke_test.py`) và hỗ trợ rollback nhanh dưới 5 phút.

### 2.3. Giám sát & Báo động đa tầng (M5 — TASK-006)
* **Telemetry toàn diện:** Tự động thu thập Metrics (Prometheus), Distributed Traces (Tempo, OpenTelemetry) và Logs (Loki) có tương quan Trace ID.
* **Grafana Dashboards:** Trực quan hóa tỷ lệ lỗi HTTP 5xx, p95/p99 latency, RPS và tài nguyên hệ thống.
* **Alertmanager & Webhooks:** Rule cảnh báo `BookingHighHttpErrorRate` và Blackbox Exporter `ApiProbeDown` tích hợp gửi tin nhắn khẩn cấp vào kênh Discord.

### 2.4. Khả năng phục hồi & Diễn tập sự cố (M6 — TASK-007)
* **Thử tải tham chiếu (E15):** Đạt p95 = 35,8 ms < 500 ms trong 10 phút tải liên tục 10 RPS với 0% lỗi 5xx.
* **Diễn tập sự cố chính thức (Official Drill):** Tiêm lỗi 20% HTTP 500 trên Demo Host, hệ thống phát hiện sau 78s, thực thi Rollback hoàn tất sau 39,2s (đạt chuẩn SLO < 300s), bảo toàn 100% dữ liệu lịch hẹn cũ.
* **Tự động hóa phản ứng:** Hỗ trợ kích hoạt rollback tự động thông qua webhook `repository_dispatch` (`trigger_rollback_dispatch.py`).

---

## 3. Danh mục Bằng chứng Nghiệm thu (Evidence Traceability)

Toàn bộ 16 cam kết thiết kế đã được chứng minh bằng văn bản và log thực nghiệm:
- **E01–E05:** [Kiểm chứng API & Transaction Database](../evidence/2026-10-07-booking-api.md)
- **E06:** [Kiểm chứng UI & E2E Integration](../evidence/frontend/2026-11-01-week3-frontend-hardening.md)
- **E07, E13:** [Kiểm chứng CI Pipeline & Volume Persistence](../evidence/2026-10-21-container-ci.md)
- **E08:** [Kiểm chứng Deploy lên Demo Host](../evidence/2026-10-28-e08-demo-deploy.md)
- **E09, E10:** [Kiểm chứng Telemetry & Collector Outage](../evidence/observability/2026-10-22-local-e09.md)
- **E11, E12, E14, E16:** [Báo cáo Diễn tập Sự cố Chính thức](../incidents/2026-11-23-official-drill-report.md)
- **E15:** [Báo cáo Thử tải 10 phút](../evidence/loadtest/2026-11-02-e15-latency-report.md)

---

## 4. Hướng dẫn Triển khai nhanh

```bash
# 1. Kéo mã nguồn phiên bản v1.0.0
git checkout v1.0.0

# 2. Triển khai ứng dụng sản xuất với Docker Compose
docker compose -f deploy/compose.production.yaml up -d

# 3. Kiểm tra tính sẵn sàng của dịch vụ
python -m scripts.smoke_test --base-url http://localhost
```
