# Incident Report Template — SE2026-T29

## 1. Thông tin chung (Overview)

| Trường | Giá trị |
| --- | --- |
| **Mã sự cố (ID)** | INC-YYYYMMDD-01 |
| **Tiêu đề** | [Tóm tắt ngắn gọn sự cố] |
| **Ngày xảy ra** | YYYY-MM-DD |
| **Mức độ nghiêm trọng (Severity)** | SEV-1 (Critical) / SEV-2 (Major) / SEV-3 (Minor) |
| **Chỉ huy sự cố (Incident Commander)** | Nguyễn Việt Anh |
| **Đội ứng cứu (Responder Team)** | Phạm Minh Cương, Lê Văn Cường, Nguyễn Mai Hoàng Anh, Vũ Thành Công |
| **Thời gian bắt đầu (T0)** | YYYY-MM-DDTHH:MM:SSZ |
| **Thời gian phát hiện (T1)** | YYYY-MM-DDTHH:MM:SSZ (Alertmanager / Prometheus) |
| **Thời gian quyết định rollback (T2)** | YYYY-MM-DDTHH:MM:SSZ |
| **Thời gian rollback hoàn tất (T3)** | YYYY-MM-DDTHH:MM:SSZ |
| **Thời gian khôi phục hoàn toàn (T4)** | YYYY-MM-DDTHH:MM:SSZ |
| **Tổng thời gian khôi phục (MTTR)** | X phút Y giây (Mục tiêu: < 5 phút) |
| **Phiên bản gây lỗi** | v0.2.0-drill (Commit: `<commit_sha>`) |
| **Phiên bản khôi phục (Rollback target)** | v0.2.0 (Commit: `<commit_sha>`) |

---

## 2. Tóm tắt sự cố (Executive Summary)

Mô tả ngắn gọn về những gì đã xảy ra, ảnh hưởng đối với người dùng và cách hệ thống đã được phục hồi.

---

## 3. Mốc thời gian chi tiết (Timeline)

| Mốc thời gian (UTC) | Sự kiện | Ghi chú & Bằng chứng liên kết |
| --- | --- | --- |
| **T0 (+00:00)** | Triển khai phiên bản drill có fault (`v0.2.0-drill`) | Kích hoạt `BOOKING_FAULT_MODE=error`, rate=0.2 |
| **T1 (+01:15)** | Cảnh báo Alertmanager phát hỏa (Firing) | Alert: `BookingHighHttpErrorRate` trên Prometheus |
| **T2 (+02:00)** | Nhóm xác nhận sự cố và bắt đầu điều tra | Xem trace lỗi trên Grafana Tempo, log 500 trên Loki |
| **T3 (+02:45)** | Quyết định kích hoạt Rollback | Chạy workflow Rollback Deployment trên GitHub Actions |
| **T4 (+04:30)** | Rollback hoàn tất, container recreate và sẵn sàng | Smoke test pass, `/api/version` trả về bản ổn định |
| **T5 (+05:00)** | Kiểm tra tính toàn vẹn dữ liệu đặt lịch | `booking_integrity.py` xác nhận 100% booking cũ còn nguyên |

---

## 4. Tác động hệ thống & Người dùng (Impact Analysis)

* **Tỷ lệ lỗi (Error Rate):** Đạt đỉnh ~20% HTTP 500 trên route `POST /api/appointments`.
* **Ảnh hưởng độ trễ (Latency):** p95 latency biến thiên trong khoảng `... ms`.
* **Dữ liệu bị ảnh hưởng:** Không có dữ liệu nào bị mất hoặc thay đổi trái phép.

---

## 5. Dấu hiệu phát hiện & Điều tra (Detection & Observability)

* **Cảnh báo (Alerts):**
  - Tên alert: `BookingHighHttpErrorRate`
  - Kênh nhận cảnh báo: Discord Webhook / Alertmanager UI
* **Tương quan giám sát (Logs, Metrics, Traces):**
  - **Prometheus Metric:** `http_server_requests_total{status="500"}` tăng vọt.
  - **Loki Log Query:** `{compose_service="backend"} |= "status=500"` hiển thị lỗi do Fault Injection.
  - **Tempo Trace:** Trace ID `<trace_id>` có span lỗi tại `inject_fault`.

---

## 6. Nguyên nhân gốc rễ (Root Cause Analysis - 5 Whys)

1. **Tại sao dịch vụ trả về 500?** Do cờ fault injection được kích hoạt trong release manifest.
2. **Tại sao cờ fault injection được đưa vào manifest?** Do diễn tập theo kế hoạch độ tin cậy E12/E14.
3. **Tại sao hệ thống khôi phục được nhanh chóng?** Nhờ quy trình rollback tự động theo release manifest trước đó và volume database được bảo toàn độc lập.

---

## 7. Khôi phục & Đối soát tính toàn vẹn (Recovery & Integrity)

* Quy trình rollback thực hiện: `python -m scripts.rollback --target-manifest previous-manifest.json`.
* Kết quả kiểm tra sức khỏe hệ thống: Smoke test pass 100%.
* Kết quả đối soát dữ liệu: Chạy `scripts/booking_integrity.py` khớp 100% snapshot trước sự cố.

---

## 8. Hành động tiếp theo (Action Items)

| STT | Hành động cải tiến | Người phụ trách | Hạn hoàn thành | Trạng thái |
| :---: | :--- | :--- | :---: | :---: |
| 1 | Bổ sung cảnh báo tự động phát hiện tỷ lệ huỷ lịch bất thường | Vũ Thành Công | YYYY-MM-DD | Todo |
| 2 | Tối ưu thời gian recreate container để giảm downtime xuống dưới 30s | Nguyễn Mai Hoàng Anh | YYYY-MM-DD | Todo |
| 3 | Tự động hóa snapshot integrity check trước mỗi lần deploy | Nguyễn Việt Anh | YYYY-MM-DD | Todo |
