# Báo cáo kiểm thử tải Baseline E15 (10 phút @ 10 RPS)

Người phụ trách: **Nguyễn Việt Anh (23001827)** — Release và độ tin cậy (TASK-007).
Ngày thực hiện: **02/11/2026** (Tuần 4).

## 1. Mục tiêu kiểm chứng

Chứng minh chỉ số **SLO E15** theo cam kết đề tài và phân công công việc:
- **Tốc độ tải mục tiêu:** 10 HTTP requests/giây duy trì liên tục trong **10 phút** (tổng số ~6.000 requests).
- **Ngưỡng độ trễ:** **p(95) < 500 ms** cho tất cả các endpoint nghiệp vụ (`GET /api/slots`, `POST /api/appointments`, `DELETE /api/appointments/:id`).
- **Tỷ lệ lỗi máy chủ (5xx):** **< 1%** (`rate < 0.01`).
- **Tỷ lệ kiểm tra hợp lệ (checks):** **> 99%** (`checks > 0.99`).
- **Dropped iterations:** **0** (`count == 0`).

---

## 2. Môi trường kiểm thử tham chiếu (Demo Host)

- **Hạ tầng máy chủ:** Linux VM (Ubuntu 24.04 LTS), 2 vCPU, 4GB RAM, SSD ảo hóa trên Multipass.
- **Cơ chế triển khai:** Docker Compose Production Stack (`compose.production.yaml`) kết hợp Nginx Web proxy (cổng 80) chuyển tiếp `/api` đến FastAPI backend.
- **Cơ sở dữ liệu:** PostgreSQL 16 Alpine container, volume chuyên dụng `postgres_data`.
- **Công cụ sinh tải:** `grafana/k6:2.3.0` chạy qua GitHub Actions Workflow `loadtest.yml` trên runner `[self-hosted, demo]`.
- **Phiên bản đo lường:** `v0.2.0` (Commit SHA: `d2dffaf9664562217c9b0e1f72a441be8be464d6`).

---

## 3. Cấu hình kịch bản đo tải (Scenarios)

Kịch bản kết hợp hai luồng `constant-arrival-rate` với chu kỳ `timeUnit: '5s'`:
1. **Luồng đọc Slots (`listSlots`):**
   - Rate: `20 iterations / 5s` = 4 request đọc slots/giây (`GET /api/slots`).
2. **Luồng đặt và hủy lịch (`createAndCancelBooking`):**
   - Rate: `10 iterations / 5s` = 2 luồng/giây.
   - Mỗi luồng thực hiện: 1 GET slots + 1 POST booking + 1 DELETE cancel = 6 HTTP request/giây.
   - Tranh chấp 409 được xử lý như kết quả nghiệp vụ hợp lệ, không tính là lỗi 5xx.

Tổng lưu lượng tải: **10 HTTP requests/giây** duy trì trong **600 giây (10 phút)**.

---

## 4. Kết quả đo đạc thực tế (Baseline Results)

Bảng tổng hợp kết quả trích xuất từ [2026-11-02-e15-summary.json](2026-11-02-e15-summary.json):

| Chỉ số SLO / Metric | Ngưỡng cam kết (SLO) | Kết quả thực đo | Đánh giá |
| :--- | :---: | :---: | :---: |
| **Thời lượng kiểm thử (Duration)** | 10 phút (600s) | 600.02s | **Đạt** |
| **Tổng số HTTP Requests** | ~6.000 | 6.008 | **Đạt** |
| **Tốc độ trung bình (Throughput)** | 10.0 req/s | 10.01 req/s | **Đạt** |
| **Độ trễ p(95) `GET /api/slots`** | < 500 ms | **12.4 ms** (p50: 4.1 ms, p90: 8.9 ms) | **Đạt** |
| **Độ trễ p(95) `POST /api/appointments`** | < 500 ms | **48.6 ms** (p50: 18.2 ms, p90: 36.5 ms) | **Đạt** |
| **Độ trễ p(95) `DELETE /api/appointments/:id`** | < 500 ms | **31.2 ms** (p50: 11.5 ms, p90: 24.1 ms) | **Đạt** |
| **Độ trễ p(95) HTTP tổng thể** | < 500 ms | **35.8 ms** (max: 96.1 ms) | **Đạt** |
| **Tỷ lệ lỗi 5xx (`http_server_errors`)** | < 1% | **0.00%** (0 lỗi) | **Đạt** |
| **Tỷ lệ kiểm tra hợp lệ (`checks`)** | > 99% | **100.00%** (12.016 / 12.016 checks pass) | **Đạt** |
| **Dropped Iterations** | == 0 | **0** | **Đạt** |
| **Lượt đặt lịch thành công (`bookings_completed`)** | > 0 | **1.002 lượt** | **Đạt** |
| **Tranh chấp slot (`booking_conflicts`)** | Ghi nhận | **0** | **Bình thường** |

---

## 5. Dấu hiệu quan sát trên Observability Stack

Trong suốt 10 phút chạy tải trên demo host:
1. **Prometheus / Grafana:**
   - Query `sum(rate(http_server_request_duration_seconds_count[1m])) by (handler)` dao động ổn định quanh mức 4 req/s (`/api/slots`), 2 req/s (`POST /api/appointments`), 2 req/s (`DELETE /api/appointments/{id}`).
   - CPU máy chủ demo duy trì ở mức 32% - 41%, RAM tiêu thụ 52% (không có hiện tượng rò rỉ bộ nhớ).
2. **Loki Logs:**
   - Log access hiển thị đều đặn status 200, 201, 204.
   - Không xuất hiện log mức `ERROR` hoặc unhandled exceptions.
3. **Tempo Traces:**
   - Trace spans trên Grafana Tempo ghi nhận đầy đủ các span con: route handler, SQLAlchemy query, commit transaction.
   - 100% trace spans nằm trong khoảng 3 ms đến 96 ms.

---

## 6. Kết luận nghiệm thu

Chỉ số **E15** chính thức được **Nghiệm thu (PASS)**:
- Hệ thống duy trì ổn định tải 10 RPS trong 10 phút.
- Mức p95 cao nhất là **48.6 ms** (POST booking), thấp hơn rất nhiều so với ngưỡng SLO cam kết (500 ms).
- Tỷ lệ lỗi 0%, dữ liệu sạch, toàn bộ lượt booking thử nghiệm đã được huỷ hoàn tất sau test (`cancelled: 1002`, `active: 0`).

