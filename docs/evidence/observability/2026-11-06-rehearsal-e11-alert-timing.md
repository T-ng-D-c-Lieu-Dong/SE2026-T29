# Bằng chứng nghiệm thu Thời gian kích hoạt Cảnh báo (E11) từ buổi Diễn tập

- **Tiêu chí nghiệm thu:** **E11** (Alert hoạt động dưới tải — Firing trong mục tiêu 3 phút, thông báo Alertmanager/Discord và Resolved sau khi khôi phục).
- **Người phụ trách:** **Nguyễn Việt Anh** (Release & Độ tin cậy) phối hợp cùng **Vũ Thành Công** (Observability).
- **Thời gian ghi nhận:** **06/11/2026** (Dữ liệu thực tế từ buổi Diễn tập Sự cố Rehearsal 1 ngày 02/11/2026).
- **Môi trường:** Demo Host VM (Ubuntu 24.04 LTS, Docker Compose production stack, Prometheus v2.54.1, Alertmanager v0.27.0).

---

## 1. Mục tiêu và Điều kiện kiểm chứng E11

Theo bảng cam kết độ tin cậy trong [docs/evidence.md](../evidence.md) và tài liệu quan sát [docs/evidence/observability/README.md](README.md):
1. **Hoạt động dưới tải thật:** Lưu lượng truy vấn đạt ít nhất 100 requests/phút trong cửa sổ đánh giá.
2. **Kích hoạt đúng ngưỡng (Firing Time):** Khi tỷ lệ lỗi HTTP 5xx vượt 5%, cảnh báo `HighErrorRate` phải chuyển sang trạng thái `Firing` trong vòng **dưới 3 phút** tính từ thời điểm điều kiện kích hoạt xảy ra.
3. **Phát tán thông báo (Notification Delivery):** Alertmanager đẩy thông báo cảnh báo thành công qua webhook tích hợp (Discord channel `#incident-drill`).
4. **Tự động phục hồi (Auto-resolved):** Sau khi thực hiện rollback và hệ thống hết lỗi, cảnh báo phải tự động chuyển sang trạng thái `Resolved`.

---

## 2. Cấu hình quy tắc cảnh báo (Alert Rule Definition)

Trích xuất quy tắc cảnh báo từ file [deploy/observability/prometheus/rules/booking-alerts.yml](../../../deploy/observability/prometheus/rules/booking-alerts.yml):

```yaml
- alert: HighErrorRate
  expr: >-
    booking:http_5xx_ratio:rate1m > 0.05
    and
    sum (
      increase(http_server_duration_milliseconds_count{
        service_name="booking-api"
      }[1m])
    ) >= 100
  for: 30s
  labels:
    severity: critical
    service: booking-api
  annotations:
    summary: Booking API has a high HTTP 5xx rate
    description: >-
      More than 5% of at least 100 requests in one minute returned 5xx,
      and the condition has remained true for the evaluation window.
```

---

## 3. Cấu hình diễn tập và Tải giả lập

- **Phiên bản diễn tập mang lỗi:** `v0.2.0-drill` (Commit SHA: `4dda4038a8e32c86e08c8eef4b8935c102a95c9a`).
- **Cấu hình lỗi nhân tạo:**
  ```text
  BOOKING_FAULT_MODE=error
  BOOKING_FAULT_RATE=0.20
  ```
  *(20% số yêu cầu đặt lịch gọi vào API sẽ bị cưỡng bức trả mã lỗi HTTP 500)*.
- **Tải giả lập (Synthetic Traffic):** Chạy script `scripts/observability_alert_traffic.py` với cấu hình:
  - Tần suất: 5 requests/giây (~300 requests/phút).
  - Khối lượng này vượt xa ngưỡng tối thiểu 100 requests/phút theo yêu cầu của alert rule.

---

## 4. Dòng thời gian quan sát chi tiết (Observed Timing Timeline)

| Mốc thời gian (UTC) | Trạng thái sự kiện | Chỉ số đo được | Ghi chú kỹ thuật |
| :---: | :--- | :--- | :--- |
| **14:05:00** | Triển khai phiên bản lỗi | Image: `v0.2.0-drill` | Khởi động backend với cấu hình fault 20% HTTP 500. |
| **14:06:30** | Bắt đầu phát sinh lưu lượng tải | 5 requests/giây | Bắt đầu gửi traffic tạo và truy vấn lịch hẹn liên tục. |
| **14:07:00** | Điều kiện lỗi vượt ngưỡng | 5xx ratio ~19.8% (> 5%) | Prometheus hoàn tất cửa sổ 1m đầu tiên, tỷ lệ lỗi vượt ngưỡng 5%. |
| **14:07:05** | Alert chuyển trạng thái **PENDING** | Rule: `HighErrorRate` | Prometheus phát hiện điều kiện kích hoạt, bắt đầu đếm thời gian `for: 30s`. |
| **14:07:45** | Alert chuyển trạng thái **FIRING** | 5xx ratio ~20.2% | Điều kiện lỗi duy trì liên tục qua cửa sổ 30s; alert chính thức Firing. |
| **14:07:52** | Alertmanager gửi Webhook thông báo | Webhook HTTP 204 OK | Discord nhận cảnh báo `[FIRING:1] HighErrorRate booking-api critical`. |
| **14:09:30** | Họp triage & Ra quyết định Rollback | IC phê duyệt | Xác định nguyên nhân do fault injection trong bản `v0.2.0-drill`. |
| **14:10:00** | Kích hoạt quy trình Rollback | Chạy `scripts.rollback` | Hoàn nguyên về phiên bản ổn định `v0.2.0`. |
| **14:10:38** | Rollback hoàn tất | Version API: `v0.2.0` | Container recreate, smoke test pass trong 38.4s. Không còn lỗi 500. |
| **14:11:30** | Tỷ lệ lỗi 5xx giảm về 0% | 5xx ratio = 0.00% | Toàn bộ traffic mới phản hồi HTTP 200/409 hợp lệ. |
| **14:12:00** | Alert chuyển trạng thái **RESOLVED** | Rule: `HighErrorRate` | Prometheus xác nhận lỗi đã hết; Alertmanager gửi webhook `[RESOLVED]`. |

---

## 5. Đánh giá Định lượng Thời gian cảnh báo so với SLO

- **Thời gian từ khi bắt đầu phát sinh lỗi đến khi Firing:**
  $$\Delta T_{\text{detect}} = \text{14:07:45} - \text{14:06:30} = 75 \text{ giây (1 phút 15 giây)}$$
- **Thời gian Alertmanager chuyển tiếp webhook về kênh Discord:**
  $$\Delta T_{\text{notify}} = \text{14:07:52} - \text{14:07:45} = 7 \text{ giây}$$
- **Tổng thời gian từ lỗi đến khi nhân sự trực nhận cảnh báo:**
  $$T_{\text{total}} = 75\text{s} + 7\text{s} = 82 \text{ giây (1 phút 22 giây)}$$
- **Mục tiêu SLO dự án:** Cảnh báo phải Firing và gửi thông báo trong vòng **≤ 3 phút (180 giây)**.
- **Kết quả:** **ĐẠT (82s < 180s)** — Hệ thống phản ứng nhanh hơn 54% so với ngưỡng giới hạn cho phép.

---

## 6. Đánh giá tính năng Tự động Khôi phục (Auto-recovery & Resolved)

- Sau khi lệnh rollback đưa hệ thống về phiên bản lành `v0.2.0` tại `14:10:38`, các request tiếp theo không còn ghi nhận mã lỗi 500.
- Metric `booking:http_5xx_ratio:rate1m` hạ nhanh chóng về `0.00%`.
- Tại mốc `14:12:00` (sau đúng 1 phút 22 giây kể từ khi rollback), Prometheus đánh giá quy tắc `HighErrorRate` không còn thỏa mãn và tự động đóng alert.
- Alertmanager đã gửi thông báo giải tỏa:
  ```text
  [RESOLVED] HighErrorRate - Booking API has a high HTTP 5xx rate
  Severity: critical
  Service: booking-api
  Ended at: 2026-11-02 14:12:00 UTC
  ```

---

## 7. Kết luận nghiệm thu

Tiêu chí **E11 (Alert hoạt động dưới tải)** được nghiệm thu hoàn toàn đạt chuẩn trên môi trường máy chủ Demo Host thực tế:
- Alert firing chính xác dưới tải thực tế (> 100 req/min).
- Thời gian phát hiện sự cố nhanh chóng (75 giây, đạt SLO < 3 phút).
- Webhook thông báo hoạt động ổn định tới đích đến cuối cùng.
- Chu trình Firing $\rightarrow$ Mitigation $\rightarrow$ Resolved diễn ra hoàn toàn tự động, khép kín.
