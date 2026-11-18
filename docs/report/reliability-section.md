# Đóng góp Kỹ thuật Độ tin cậy (Reliability Section) — Báo cáo Tổng kết Dự án

- **Người phụ trách**: **Nguyễn Việt Anh (MSSV: 23001827)**
- **Vai trò**: Release Engineer & Reliability Lead (TASK-005, TASK-007)
- **Mốc nghiệm thu**: **M4 (Release + Deploy)** và **M6 (Reliability Demo)**
- **Dự án**: SE2026-T29 (Hệ thống đặt lịch hẹn trực tuyến — Booking System)

---

## 1. Mục tiêu và Tiêu chuẩn Độ tin cậy (SLO & Targets)

Hệ thống đặt mục tiêu đáp ứng các chỉ tiêu chất lượng dịch vụ (Service Level Objectives - SLO) khắt khe nhằm đảm bảo tính sẵn sàng cao, khả năng tự phát hiện lỗi và khôi phục nhanh chóng:

| Chỉ số độ tin cậy (SLI) | Ngưỡng cam kết (SLO) | Kết quả thực nghiệm thực tế | Trạng thái nghiệm thu |
| :--- | :--- | :--- | :---: |
| **Độ trễ phản hồi (p95 Latency)** | $\le 500\text{ ms}$ tại 10 req/s liên tục trong 10 phút | **35,8 ms** (p99 = 48,2 ms) | **Đạt** (E15) |
| **Tỷ lệ lỗi dịch vụ (5xx Error Rate)** | $< 1\%$ trong điều kiện tải bình thường | **0,00%** lỗi 5xx | **Đạt** (E15) |
| **Thời gian phát hiện sự cố (MTTD)** | $< 180\text{ s}$ (3 phút) kể từ khi xuất hiện lỗi | **78 giây** (Firing + Webhook Discord) | **Đạt** (E11) |
| **Thời gian khôi phục dịch vụ (MTTR)** | $< 300\text{ s}$ (5 phút) cho toàn bộ quy trình rollback | **39,20 giây** (Recreate + Smoke pass) | **Đạt** (E12) |
| **Bảo toàn dữ liệu (Data Preservation)** | $100\%$ dữ liệu đặt lịch hẹn cũ không bị mất sau sự cố | **100%** (32/32 bookings khớp nguyên vẹn) | **Đạt** (E13, E14) |
| **Phát hiện sập dịch vụ (Outage Detection)** | $< 60\text{ s}$ khi container chết dù không có lưu lượng | **45 giây** qua Blackbox Exporter Probe | **Đạt** (E16) |

---

## 2. Kiến trúc Độ tin cậy & Cơ chế Phòng vệ (Reliability Architecture)

1. **Định danh phát hành bất biến (Immutable Release Manifests):**
   - Mọi bản dựng triển khai đều được neo chặt bởi commit SHA và SHA256 digest của hình ảnh Docker, loại bỏ hoàn toàn hiện tượng trôi phiên bản do dùng tag `latest`.
   - Cấu trúc Release Manifest lưu trữ rõ ràng migration revision, cấu hình fault và thời gian phát hành.
2. **Quy trình Rollback tất định & Tự động (Deterministic Automated Rollback):**
   - Hỗ trợ cả 2 phương thức: kích hoạt qua CLI an toàn có khóa chống xung đột (`deploy_lock.py`) và kích hoạt tự động từ xa thông qua webhook `repository_dispatch` khi Alertmanager phát hỏa kéo dài.
   - Script rollback tự động thẩm định chỉ tiêu SLO thời gian (`verify_rollback_slo.py`) và kiểm tra sức khỏe nghiệp vụ bằng `smoke_test.py` trước khi bàn giao lưu lượng.
3. **Phòng vệ cơ sở dữ liệu & Tương thích ngược Schema (Zero Data Loss Migration):**
   - Tuân thủ nghiêm ngặt chính sách migration: Mọi thay đổi schema bảng PostgreSQL đều phải hỗ trợ tương thích ngược (backward-compatible) với mã nguồn của phiên bản trước đó trong cửa sổ rollback, không thực hiện drop column/table nguy hiểm.
4. **Quan sát đa tầng tương quan (Correlated Full-stack Observability):**
   - Tích hợp OpenTelemetry tự động gắn Trace ID vào response header và log ngữ cảnh.
   - Chuỗi truy vết: Alertmanager Notification → Prometheus Metrics Spike → Grafana Tempo Trace Span → Loki Stacktrace Log, giúp khoanh vùng nguyên nhân gốc rễ (RCA) trong dưới 1 phút.

---

## 3. Tổng hợp Bằng chứng Thực nghiệm (Empirical Evidence)

Toàn bộ các cam kết kỹ thuật của mốc M4 và M6 đã được kiểm chứng bằng số liệu và log đo lường thực tế trên môi trường máy chủ Demo Host (`booking-demo`, Ubuntu 24.04 LTS):

* **[Báo cáo đo tải chuẩn 10 phút (E15)](../evidence/loadtest/2026-11-02-e15-latency-report.md):** 6.000 requests, p95 35,8ms, 0 lỗi 5xx.
* **[Báo cáo diễn tập sự cố chính thức](../incidents/2026-11-23-official-drill-report.md):** Diễn tập toàn trình 5 giai đoạn, kích hoạt lỗi 20% HTTP 500, phát hiện sau 78s, rollback hoàn tất sau 39,2s, bảo toàn 100% dữ liệu đặt lịch.
* **[Bảng tổng hợp Manifests & Workflows](../evidence/2026-11-25-manifests-and-workflows.md):** Lưu trữ định danh `v0.1.0`, `v0.2.0-drill`, `v0.2.1` và liên kết trực tiếp tới các workflow GitHub Actions.

---

## 4. Kết luận về Tính sẵn sàng (Production Readiness Conclusion)

Hệ thống đặt lịch hẹn trực tuyến SE2026-T29 đã hoàn thành xuất sắc tất cả các bài kiểm tra thực nghiệm về độ tin cậy trong phạm vi đồ án Production Readiness Lab:
- Pipeline CI/CD tự động hóa hoàn chỉnh từ commit, lint, test, release manifest đến deploy và rollback.
- Đội ngũ vận hành nắm vững quy trình phản ứng sự cố thông qua tài liệu phân vai, danh mục kiểm tra và diễn tập thực tế.
- Hệ thống chính thức sẵn sàng đóng gói phiên bản ổn định **v1.0.0**.
