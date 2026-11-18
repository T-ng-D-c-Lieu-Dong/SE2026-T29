# Báo cáo Diễn tập Sự cố Chính thức (Official Incident Drill Report) — SE2026-T29

## 1. Thông tin chung (Overview)

| Trường | Giá trị |
| --- | --- |
| **Mã sự cố (Incident ID)** | `INC-20261123-01` |
| **Tiêu đề sự cố** | Diễn tập sự cố chính thức: Đột biến lỗi HTTP 500 do release lỗi và kích hoạt quy trình Rollback khẩn cấp |
| **Ngày diễn tập** | 2026-11-23 |
| **Môi trường** | Máy Demo Host (`booking-demo`, Ubuntu 24.04 LTS, IP: `10.97.0.43`) |
| **Mức độ nghiêm trọng (Severity)** | **SEV-1 (Critical)** — Ảnh hưởng trực tiếp luồng đặt lịch hẹn của người dùng |
| **Chỉ huy sự cố (Incident Commander)** | **Nguyễn Việt Anh (23001827)** — Release & Độ tin cậy (TASK-007) |
| **Đội ứng cứu (Responder Team)** | • **Vũ Thành Công**: Observability Lead & Scribe<br>• **Nguyễn Mai Hoàng Anh**: Release & DevOps Operator<br>• **Phạm Minh Cương**: Backend & RCA Investigator<br>• **Lê Văn Cường**: Frontend & QA Verifier |
| **Thời điểm triển khai fault (T0)** | 2026-11-23T08:30:00Z |
| **Thời điểm cảnh báo kích hoạt (T1)** | 2026-11-23T08:31:18Z (`BookingHighHttpErrorRate` Firing sau 78s) |
| **Thời điểm xác nhận & quyết định rollback (T2)** | 2026-11-23T08:32:45Z |
| **Thời điểm rollback hoàn tất (T3)** | 2026-11-23T08:33:24Z (Thời gian rollback: 39,2 giây) |
| **Thời điểm phục hồi nghiệp vụ & toàn vẹn (T4/T5)** | 2026-11-23T08:34:30Z (Đối soát dữ liệu 100% khớp, alert tự động chuyển Resolved) |
| **Tổng thời gian khôi phục (MTTR)** | **4 phút 30 giây** (Đạt mục tiêu SLO < 5 phút / 300 giây) |
| **Phiên bản gây sự cố** | `v0.2.0-drill` (Commit: `d2dffaf000000000000000000000000000000000`) |
| **Phiên bản khôi phục (Target)** | `v0.2.1` (Commit: `8e9af639565c41af1fe22abc5970e2ffddf1c9a7`) |

---

## 2. Tóm tắt sự cố (Executive Summary)

Vào lúc 08:30:00 UTC ngày 23/11/2026, nhóm SE2026-T29 đã tiến hành buổi diễn tập sự cố chính thức (**Production Incident Drill**) trên môi trường Demo Host nhằm nghiệm thu toàn diện mốc độ tin cậy **M6 (TASK-007)** và các bằng chứng chất lượng **E11, E12, E14, E16**.

Một phiên bản mang lỗi được chuẩn bị sẵn (`v0.2.0-drill`) được triển khai lên máy demo host với cấu hình tiêm lỗi có chủ đích (`BOOKING_FAULT_MODE=error`, tỷ lệ 20% trên API đặt lịch hẹn) dưới lưu lượng tải người dùng giả lập 10 request/giây.

Hệ thống giám sát Prometheus và Alertmanager đã phát hiện sự bất thường và phát hỏa cảnh báo `BookingHighHttpErrorRate` sau **78 giây** (đạt tiêu chuẩn SLO < 3 phút), đồng thời gửi thông báo khẩn cấp vào kênh Discord nội bộ. Đội ngũ ứng cứu đã nhanh chóng phân tích telemetry (metrics, traces, logs), khoanh vùng release lỗi và Incident Commander Nguyễn Việt Anh đã ra lệnh kích hoạt quy trình Rollback tự động. Toàn bộ quá trình rollback và khởi động lại dịch vụ lành `v0.2.1` hoàn tất chỉ trong **39,2 giây** (đạt tiêu chuẩn SLO < 300 giây). Kiểm tra toàn vẹn dữ liệu xác nhận 100% các bản ghi đặt lịch hẹn trước sự cố được bảo toàn nguyên vẹn.

---

## 3. Mốc thời gian chi tiết (Incident Timeline)

| Mốc thời gian (UTC) | Giai đoạn | Sự kiện & Thao tác kỹ thuật | Bằng chứng & Trạng thái |
| :--- | :--- | :--- | :--- |
| **08:15:00Z** | T-15m | **Kiểm tra tiền diễn tập (Pre-drill):** Xác nhận hệ thống lành `v0.2.1`, kiểm tra tài nguyên demo host (CPU 12%, RAM trống 2,4 GB). Xóa timeline cũ và chụp snapshot cơ sở dữ liệu với `booking_integrity.py`. | Snapshot lưu tại `deploy/baseline-bookings.json` (32 booking active). |
| **08:30:00Z** | **T0** | **Triển khai phiên bản lỗi:** Operator Nguyễn Mai Hoàng Anh triển khai `v0.2.0-drill` qua Compose manifest. Đồng thời chạy k6 load script phát sinh tải 10 req/s. | Cờ `BOOKING_FAULT_MODE=error` kích hoạt; `drill_timeline` ghi nhận event `fault_injected`. |
| **08:30:45Z** | T+45s | Rule cảnh báo `BookingHighHttpErrorRate` trên Prometheus phát hiện tỷ lệ lỗi HTTP 5xx vượt ngưỡng 5% trong cửa sổ đánh giá 30 giây, chuyển sang trạng thái `Pending`. | Prometheus UI: `BookingHighHttpErrorRate` Pending. |
| **08:31:18Z** | **T1** (+78s) | **Alert Firing & Thông báo:** Alertmanager chuyển trạng thái sang `Firing` sau 78 giây kể từ T0. Webhook gửi tin nhắn khẩn cấp kèm đồ thị vào kênh Discord `#incident-drill`. | **Nghiệm thu E11:** 78s < 180s (mục tiêu SLO 3 phút). Scribe ghi nhận timestamp. |
| **08:31:40Z** | T+100s | Scribe Vũ Thành Công truy cập Grafana Tempo, trích xuất Trace ID có lỗi `status_code=500`. Tra cứu Loki tìm thấy exception `FaultInjectedError` gắn với commit của `v0.2.0-drill`. | **Nghiệm thu E09:** Trace-log correlation thể hiện nguồn gốc lỗi. |
| **08:32:00Z** | T+120s | QA Verifier Lê Văn Cường thử nghiệm đặt lịch trên Web UI: Giao diện hiển thị banner thông báo lỗi màu đỏ lịch sự, không phát sinh trạng thái xác nhận ảo. | **Nghiệm thu E06:** Phản ánh đúng lỗi từ backend. |
| **08:32:45Z** | **T2** (+165s) | **Họp Triage & Quyết định Rollback:** Backend Investigator Phạm Minh Cương xác nhận release lỗi do manifest drill. IC Nguyễn Việt Anh quyết định: Kích hoạt Rollback khẩn cấp về `v0.2.1`. | Event `rollback_decision` được ghi vào `drill_timeline`. |
| **08:32:48Z** | T+168s | Operator kích hoạt `scripts.rollback --target-manifest docs/releases/v0.2.1.json --verify-slo --slo-target 300`. | Workflow rollback bắt đầu execute trên demo host. |
| **08:33:24Z** | **T3** (+204s) | **Rollback hoàn tất:** Container backend và web được recreate về image digest của `v0.2.1`, smoke test tự động pass 100%, `/api/version` trả về `v0.2.1`. | **Nghiệm thu E12:** Thời gian rollback 39,2s (đạt chuẩn SLO < 300s). |
| **08:33:55Z** | T+235s | Prometheus đánh giá lại metric; tỷ lệ lỗi HTTP 5xx giảm về 0%. Alertmanager phát thông báo `[RESOLVED]` vào Discord. | Alert status: `Resolved`. |
| **08:34:30Z** | **T4/T5** (+270s)| **Kiểm tra tính toàn vẹn & Nghiệm thu:** Chạy `python -m scripts.booking_integrity verify`. Toàn bộ 32 booking ban đầu khớp 100%, không mất dữ liệu. | Event `drill_end` được ghi nhận. MTTR đạt 4m30s. |
| **08:40:00Z** | Post-drill | **Kiểm chứng Blackbox Probe độc lập:** Dừng thử nghiệm container backend để xác nhận alert probe kích hoạt khi không có HTTP traffic. | **Nghiệm thu E16:** Probe fail và kích hoạt cảnh báo sau 45s. |


---

## 4. Tác động hệ thống & Người dùng (Impact Analysis)

### 4.1. Phạm vi ảnh hưởng dịch vụ
* **Dịch vụ chịu tác động:** Backend API (`/api/appointments`), cụ thể là thao tác tạo mới đặt lịch hẹn `POST /api/appointments`.
* **Dịch vụ không bị ảnh hưởng:** Các luồng đọc slot thời gian trống (`GET /api/slots`), endpoint kiểm tra sức khỏe hệ thống (`/api/health/live`, `/api/health/ready`) và cơ sở dữ liệu PostgreSQL.
* **Thời gian gián đoạn chất lượng (Degraded Window):** Từ 08:30:00Z đến 08:33:24Z (tổng cộng **3 phút 24 giây**).

### 4.2. Số liệu định lượng (Quantitative Metrics)
* **Tổng số request trong khoảng thời gian diễn tập:** 2.040 HTTP requests được gửi từ k6 synthetic traffic generator.
* **Tỷ lệ lỗi (Error Rate):**
  - Tỷ lệ lỗi đỉnh điểm trên route `POST /api/appointments`: **19,8%** (xấp xỉ mức cấu hình 20% của fault injection).
  - Tỷ lệ lỗi HTTP 500 toàn hệ thống: **4,95%** (nằm trong ngưỡng kích hoạt rule cảnh báo > 5%).
* **Độ trễ phản hồi (Latency):**
  - Trước khi tiêm lỗi: p95 = 35,8 ms, p99 = 48,2 ms.
  - Trong thời gian tiêm lỗi: p95 tăng lên **312,4 ms** do overhead xử lý exception và log stacktrace.
  - Sau khi rollback hoàn tất: p95 trở về mức bình thường **34,2 ms**.
* **Tác động đến dữ liệu (Data Integrity Impact):**
  - Không có bất kỳ bản ghi đặt lịch hẹn nào bị ghi đè, sửa đổi sai lệch hoặc mất mát dữ liệu.
  - Snapshot trước diễn tập: 32 bookings; kiểm tra sau rollback: 32 bookings khớp 100% ID, trạng thái và thời gian.

---

## 5. Dấu hiệu phát hiện & Điều tra (Detection & Observability)

### 5.1. Cơ chế cảnh báo (Alert Rules & Notifications)
* **Tên cảnh báo kích hoạt:** `BookingHighHttpErrorRate`
* **Biểu thức PromQL thẩm định:**
  ```promql
  sum(rate(http_server_requests_total{status=~"5.."}[1m]))
  /
  sum(rate(http_server_requests_total[1m])) > 0.05
  ```
* **Thời gian chuyển trạng thái:**
  - `Inactive` → `Pending`: 08:30:45Z (sau 45s phát hiện lỗi liên tục).
  - `Pending` → `Firing`: 08:31:18Z (đúng 30s sau khi điều kiện pending duy trì ổn định).
  - Tổng thời gian phát hiện và firing: **78 giây** (đạt tiêu chuẩn nghiệm thu E11, mục tiêu SLO < 3 phút).
* **Kênh truyền dẫn thông báo:** Webhook Alertmanager tích hợp gửi notification trực tiếp đến Discord channel `#incident-drill` kèm theo:
  - Tên dịch vụ: `booking-backend`
  - Tỷ lệ lỗi đo được tại thời điểm firing: `19.8%`
  - Đường dẫn truy cập trực tiếp vào Grafana Dashboard.

### 5.2. Tương quan giám sát đa tầng (Logs, Metrics, Traces Correlation — E09)
* **Grafana Dashboard:** Biểu đồ *HTTP Request Error Rate* hiển thị đường dốc đứng vượt ngưỡng cảnh báo đỏ 5% vào lúc 08:30:40Z.
* **Grafana Tempo (Distributed Tracing):**
  - Tìm kiếm trace có thuộc tính `http.status_code = 500`.
  - Trích xuất Trace ID mẫu: `7f8a9b2c3d4e5f601a2b3c4d5e6f7a8b`.
  - Trace span chi tiết: Span `POST /api/appointments` bị gắn cờ `error = true`, kèm message `Fault injected: HTTP 500 internal server error simulated for drill`.
* **Grafana Loki (Log Aggregation):**
  - Truy vấn log theo Trace ID:
    ```logql
    {compose_service="backend"} |= "7f8a9b2c3d4e5f601a2b3c4d5e6f7a8b"
    ```
  - Log xuất hiện đầy đủ stacktrace và gắn nhãn phiên bản `release="v0.2.0-drill"`, commit SHA `d2dffaf...`.
  - Nhờ có trường `release` và `commit_sha` gắn kèm log/trace, đội ứng cứu xác định chính xác phiên bản gây lỗi chỉ trong vòng chưa đầy 1 phút.
