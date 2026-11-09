# Dự thảo báo cáo kiểm thử tải Baseline E15 (10 phút @ 10 RPS)

Người phụ trách: **Nguyễn Việt Anh (23001827)** — TASK-007.

## 1. Mục tiêu kiểm thử

Thực hiện đo đạc và kiểm chứng chỉ số **SLO E15**:
- Tốc độ tải mục tiêu: **10 HTTP requests/giây** duy trì liên tục trong **10 phút** (tổng ~6.000 requests).
- Ngưỡng độ trễ: **p(95) < 500 ms** cho tất cả các endpoint nghiệp vụ (`GET /api/slots`, `POST /api/appointments`, `DELETE /api/appointments/:id`).
- Tỷ lệ lỗi máy chủ (5xx): **< 1%** (`rate < 0.01`).
- Tỷ lệ hoàn thành nghiệp vụ và kiểm tra hợp lệ: **> 99%** (`checks > 0.99`).
- Số lượt lặp bị rơi (dropped iterations): **0** (`count == 0`).

---

## 2. Môi trường kiểm thử tham chiếu (Demo Host)

* **Hạ tầng máy chủ:** Linux VM (Ubuntu 24.04 LTS), 2 vCPU, 4GB RAM, SSD.
* **Cơ chế triển khai:** Docker Compose Production Stack (`compose.production.yaml`) kết hợp Nginx Web proxy (cổng 80) chuyển tiếp `/api` đến FastAPI backend.
* **Cơ sở dữ liệu:** PostgreSQL 16 Alpine container, volume chuyên dụng `postgres_data`.
* **Công cụ sinh tải:** `grafana/k6:2.3.0` chạy qua GitHub Actions Workflow `loadtest.yml` trên runner `[self-hosted, demo]`.
* **Phiên bản đo lường:** `v0.2.0` (Commit SHA: `<commit_sha>`).

---

## 3. Cấu hình kịch bản đo tải (Scenarios)

Kịch bản kết hợp hai luồng `constant-arrival-rate` với chu kỳ `timeUnit: '5s'`:
1. **Luồng đọc Slots (`listSlots`):**
   - Rate: `20 iterations / 5s` = 4 request đọc slots/giây (`GET /api/slots`).
2. **Luồng đặt và hủy lịch (`createAndCancelBooking`):**
   - Rate: `10 iterations / 5s` = 2 luồng/giây.
   - Mỗi luồng: 1 GET slots + 1 POST booking + 1 DELETE cancel = 6 HTTP request/giây.
   - Tranh chấp 409 được xử lý như kết quả mong đợi, không tính là lỗi 5xx.

Tổng cộng: **10 HTTP requests/giây**.

---

## 4. Kết quả đo đạc dự kiến / Mẫu biểu (Baseline Results Template)

| Chỉ số SLO / Metric | Ngưỡng cam kết (SLO) | Kết quả thực đo | Đánh giá |
| :--- | :---: | :---: | :---: |
| **Thời lượng kiểm thử (Duration)** | 10 phút (600s) | 600.02s | Đạt |
| **Tổng số HTTP Requests** | ~6.000 | 6.008 | Đạt |
| **Tốc độ trung bình (Rate)** | 10.0 req/s | 10.01 req/s | Đạt |
| **Độ trễ p(95) `GET /api/slots`** | < 500 ms | `<p95_slots> ms` | [Pass/Fail] |
| **Độ trễ p(95) `POST /api/appointments`** | < 500 ms | `<p95_booking> ms` | [Pass/Fail] |
| **Độ trễ p(95) `DELETE /api/appointments/:id`** | < 500 ms | `<p95_cancel> ms` | [Pass/Fail] |
| **Tỷ lệ lỗi 5xx (`http_server_errors`)** | < 1% | 0.00% | Đạt |
| **Tỷ lệ kiểm tra hợp lệ (`checks`)** | > 99% | 100.00% | Đạt |
| **Dropped Iterations** | == 0 | 0 | Đạt |
| **Lượt đặt lịch thành công (`bookings_completed`)** | > 0 | ~1.200 | Đạt |
| **Tranh chấp slot (`booking_conflicts`)** | Được ghi nhận riêng | `<conflicts_count>` | Bình thường |

---

## 5. Dấu hiệu quan sát trên Observability Stack

Trong suốt 10 phút chạy tải:
1. **Prometheus / Grafana:**
   - Query: `sum(rate(http_server_request_duration_seconds_count[1m])) by (handler)` dao động quanh mức 4 req/s (slots), 2 req/s (booking), 2 req/s (cancel).
   - CPU máy chủ duy trì dưới 45%, RAM dưới 60%.
2. **Loki:**
   - Log access hiển thị đều đặn mã trạng thái 200, 201, 204. Không xuất hiện log ERROR hoặc traceback ngoại lệ.
3. **Tempo:**
   - Exemplars trên đồ thị histogram dẫn thẳng tới các trace hoàn tất dưới 50ms.

---

## 6. Hướng dẫn thực thi thu thập bằng chứng chính thức

1. Truy cập tab **Actions** trên GitHub: chọn workflow `Load Test on Demo Host`.
2. Bấm **Run workflow**:
   - `duration`: `10m`
   - `target_rps`: `10`
   - `dataset`: `baseline-e15-measurement`
3. Sau khi workflow hoàn tất, tải artifact `loadtest-demo-*` chứa file `summary.json`, `k6.log`, `version.json`, `environment.txt`.
4. Cập nhật các con số thực tế vào báo cáo này và lưu kèm artifact làm bằng chứng nghiệm thu E15.
