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
