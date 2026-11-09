# Runbook diễn tập sự cố từng bước (Step-by-Step Drill Runbook)

Tài liệu hướng dẫn thực hành diễn tập sự cố (Incident Drill E12/E14) và khôi phục hệ thống (Rollback) cho nhóm **SE2026-T29**.

Người phụ trách điều phối: **Nguyễn Việt Anh (Release & Độ tin cậy)**.

---

## 1. Mục tiêu và Tiêu chí nghiệm thu

1. **Phát hiện sự cố:** Alertmanager kích hoạt cảnh báo `BookingHighHttpErrorRate` khi tỷ lệ lỗi vượt ngưỡng.
2. **Khôi phục nhanh:** Rollback về phiên bản ổn định hoàn tất trong **dưới 5 phút (MTTR < 300s)**.
3. **Bảo toàn dữ liệu:** 100% dữ liệu lịch hẹn trước sự cố được giữ nguyên vẹn (`booking_integrity.py` pass).
4. **Bằng chứng đầy đủ:** Ghi lại timeline, metrics, log lỗi, trace ID và xuất báo cáo sự cố theo mẫu.

---

## 2. Chuẩn bị trước diễn tập (Pre-drill Checklist)

* [ ] Kiểm tra hệ thống production/demo đang ở trạng thái xanh:
  ```bash
  curl -s http://localhost/api/health/ready
  curl -s http://localhost/api/version
  ```
* [ ] Khởi tạo bộ ghi mốc thời gian diễn tập:
  ```bash
  python -m scripts.drill_timeline clear
  python -m scripts.drill_timeline record --event drill_start --description "Bắt đầu diễn tập sự cố"
  ```
* [ ] Chụp snapshot dữ liệu đặt lịch ban đầu để đối soát tính toàn vẹn:
  ```bash
  python -m scripts.booking_integrity snapshot --output /tmp/baseline-bookings.json --base-url http://localhost
  ```

---

## 3. Giai đoạn 1: Kích hoạt sự cố (Inject Fault)

1. **Cấu hình lỗi:**
   - File cấu hình [deploy/drill-fault.json](../../deploy/drill-fault.json) đã được chuẩn bị:
     ```json
     {
       "mode": "error",
       "rate": 0.2,
       "duration_seconds": 900,
       "latency_seconds": 3.0
     }
     ```
2. **Triển khai bản drill:**
   - Gắn Git tag và push:
     ```bash
     git tag -a v0.2.0-drill -m "Release v0.2.0-drill for incident rehearsal"
     git push origin v0.2.0-drill
     ```
   - Pipeline `release.yml` sẽ tự động đóng gói image và release manifest `v0.2.0-drill.json` mang cấu hình lỗi.
   - Reviewer duyệt deployment lên **demo host**.

---

## 4. Giai đoạn 2: Quan sát và Phát hiện (Observability & Alerting)

1. **Tạo lưu lượng truy vấn (Traffic Generation):**
   - Chạy kịch bản k6 tạo tải nhẹ hoặc kịch bản alert traffic:
     ```bash
     python -m scripts.observability_alert_traffic --base-url http://localhost --duration-seconds 120
     ```
2. **Ghi nhận cảnh báo:**
   - Khi Prometheus / Alertmanager phát hỏa cảnh báo `BookingHighHttpErrorRate`:
     ```bash
     python -m scripts.drill_timeline record --event alert_fired --description "Alert BookingHighHttpErrorRate firing"
     ```
3. **Điều tra nguyên nhân (Triage):**
   - Ghi nhận bắt đầu điều tra:
     ```bash
     python -m scripts.drill_timeline record --event investigation_start --description "Xem xét Grafana logs/traces"
     ```
   - Mở Grafana Dashboard:
     - **Logs:** Tìm log chứa `"status": 500` và trường `"fault_injected": true`.
     - **Traces:** Chọn trace lỗi bất thường từ exemplar trên biểu đồ HTTP requests.
     - **Version:** Kiểm tra endpoint `/api/version` thấy `fault_active: true`.

---

## 5. Giai đoạn 3: Thực hiện Rollback (Mitigation)

1. **Ghi nhận bắt đầu rollback:**
   ```bash
   python -m scripts.drill_timeline record --event rollback_start --description "Quyết định kích hoạt rollback về v0.2.0"
   ```
2. **Kích hoạt rollback:**
   - Vào GitHub Actions → chọn workflow `Rollback Deployment` → **Run workflow** (để trống target để lấy bản manifest tốt trước đó).
   - Hoặc chạy script trên máy demo host:
     ```bash
     python -m scripts.rollback --target-manifest /opt/booking/state/previous-manifest.json
     ```
3. **Rollback hoàn tất:**
   - Khi smoke test của rollback thành công (status `PASS`):
     ```bash
     python -m scripts.drill_timeline record --event rollback_complete --description "Rollback smoke test passed"
     ```

---

## 6. Giai đoạn 4: Nghiệm thu và Kiểm tra toàn vẹn (Verification)

1. **Kiểm tra tính toàn vẹn dữ liệu đặt lịch:**
   ```bash
   python -m scripts.booking_integrity verify --baseline /tmp/baseline-bookings.json --base-url http://localhost
   ```
   *Yêu cầu:* Kết quả trả về `[PASS] 100% pre-existing bookings preserved. Zero data loss.`
2. **Ghi nhận kết thúc diễn tập:**
   ```bash
   python -m scripts.drill_timeline record --event service_restored --description "Dịch vụ ổn định hoàn toàn"
   ```
3. **Xuất bảng tổng kết:**
   ```bash
   python -m scripts.drill_timeline report
   ```

---

## 7. Bàn giao và Lưu trữ bằng chứng (Post-drill Documentation)

1. Sao chép bảng Markdown từ lệnh `python -m scripts.drill_timeline report` vào file báo cáo sự cố theo mẫu [incident-report-template.md](incident-report-template.md).
2. Lưu file báo cáo vào thư mục `docs/evidence/` kèm đường dẫn run GitHub Actions và dashboard snapshots.
