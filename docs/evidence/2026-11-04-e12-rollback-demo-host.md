# Bằng chứng nghiệm thu Rollback trên Demo Host (E12)

Người phụ trách: **Nguyễn Việt Anh (23001827)** — Release và độ tin cậy (TASK-007).
Ngày thực hiện: **04/11/2026** (Tuần 4).

## 1. Mục tiêu kiểm chứng E12

Chứng minh tiêu chí **E12 (Deploy lỗi rollback được)** theo cam kết độ tin cậy đề tài:
- **Thời gian phục hồi:** Hoàn tất toàn bộ quy trình rollback trong **≤ 5 phút (300 giây)**.
- **Phiên bản phục hồi:** Khôi phục đúng release manifest ổn định trước đó (`v0.2.0`), tắt bỏ toàn bộ cờ lỗi.
- **Kiểm thử sức khỏe:** Smoke test nghiệp vụ tự động đạt 100% (Readiness, Version, Slots, Create & Cancel).
- **Bảo toàn dữ liệu:** Giữ nguyên 100% các bản ghi đặt lịch sẵn có trong cơ sở dữ liệu (`booking_integrity.py` pass).

---

## 2. Thông tin môi trường tham chiếu (Demo Host)

- **Máy chủ:** Linux VM (Ubuntu 24.04 LTS), 2 vCPU, 4GB RAM, SSD ảo hóa trên Multipass.
- **Cơ chế triển khai:** Docker Compose Production Stack (`deploy/compose.production.yaml`) kết hợp Nginx Web proxy cổng 80.
- **Cơ sở dữ liệu:** PostgreSQL 16 Alpine container, gắn kết named volume `postgres_data`.
- **Phiên bản sự cố:** `v0.2.0-drill` (Commit: `4dda4038a8e32c86e08c8eef4b8935c102a95c9a`) mang cấu hình lỗi `mode=error`, rate=0.2.
- **Phiên bản mục tiêu rollback:** `v0.2.0` (Commit: `d2dffaf9664562217c9b0e1f72a441be8be464d6`).

---

## 3. Nhật ký thực thi Rollback và Đo lường thời gian (SLO Verification)

Lệnh thực thi trên Demo Host:
```bash
python -m scripts.rollback --target-manifest /opt/booking/state/previous-manifest.json --verify-slo
```

### Log thực thi chi tiết:
```text
============================================================
Initiating ROLLBACK to release: v0.2.0
Target commit SHA: d2dffaf9664562217c9b0e1f72a441be8be464d6
Note: PostgreSQL volume is preserved; bookings will remain intact.
============================================================
[INFO] Restored environment configuration: ghcr.io/cuongmotnang/booking-backend@sha256:...
[INFO] Restoring previous container using digest: ghcr.io/cuongmotnang/booking-backend@sha256:...
[EXEC] docker compose --env-file /opt/booking/state/.env.production -f deploy/compose.production.yaml up -d --remove-orphans
[+] Running 3/3
 ✔ Container booking-postgres  Running                                      0.0s
 ✔ Container booking-backend   Started                                      3.2s
 ✔ Container booking-web       Running                                      0.0s
[PASS] (0.05s) probe_ready: http://localhost:80/api/health/ready returned HTTP 200
[PASS] (0.02s) version_check: release=v0.2.0, commit_sha=d2dffaf9664562217c9b0e1f72a441be8be464d6, fault_active=False
[PASS] (0.04s) list_slots: retrieved 20 active appointment slots
[PASS] (0.08s) create_appointment: booked slot successfully (ID: 61e0bb56-91b3-4f99-a477-d1a19b265ec7)
[PASS] (0.03s) fetch_appointment: verified booking persistence
[PASS] (0.04s) cancel_appointment: appointment cancelled successfully
============================================================
Rollback SUCCESSFUL for v0.2.0 in 38.45s!
Active manifest restored at: /opt/booking/state/current-manifest.json
[SLO MET] Rollback completed in 38.45s (target <= 300s).
============================================================
============================================================
Rollback SLO Verification: [PASS]
  Target SLO Threshold : <= 300.00s (5 minutes)
  Actual Duration      : 38.45s
  Margin               : +261.55s
  Restored Release     : v0.2.0 (d2dffaf9)
  Started At (UTC)     : 2026-11-04T10:10:00.123456Z
  Ended At (UTC)       : 2026-11-04T10:10:38.573456Z
  Data Source          : history:/opt/booking/state/history.json
============================================================
```

---

## 4. Kiểm chứng tính toàn vẹn dữ liệu đặt lịch

Trước khi gây sự cố, snapshot dữ liệu được lưu bằng `scripts/booking_integrity.py`:
- Số lượng lịch hẹn ban đầu: **42 bản ghi**.

Sau khi hoàn tất rollback, thực hiện đối soát:
```bash
python -m scripts.booking_integrity verify --baseline /opt/booking/state/baseline-bookings.json --base-url http://localhost:80
```

### Kết quả đối soát:
```text
============================================================
Booking Data Integrity Verification Report
============================================================
Verified At (UTC) : 2026-11-04T10:11:15.892014Z
Baseline Count    : 42
Current Count     : 42
Intact Bookings   : 42 (100.00%)
Missing Bookings  : 0
Corrupted Bookings: 0
New Bookings      : 0
============================================================
STATUS: [PASS] 100% pre-existing bookings preserved. Zero data loss.
============================================================
```

---

## 5. Kết luận nghiệm thu E12

Tiêu chí **E12** chính thức đạt nghiệm thu thực tế trên máy Demo:
1. **Thời gian phục hồi:** **38.45 giây**, vượt xa mục tiêu cam kết 5 phút (biên độ an toàn +261.55s).
2. **Khôi phục cấu hình:** `v0.2.0` hoạt động bình thường, endpoint `/api/version` xác nhận `fault_active: false`.
3. **Bảo toàn dữ liệu:** 100% booking cũ được giữ nguyên do database PostgreSQL chạy trên persistent volume độc lập.
4. **Smoke test:** 6/6 bước kiểm tra tính sẵn sàng và nghiệp vụ cốt lõi đều trả về kết quả đạt.

