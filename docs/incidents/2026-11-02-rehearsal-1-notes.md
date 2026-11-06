# Biên bản diễn tập sự cố lần 1 (Rehearsal 1 Notes)

- **Thời gian diễn tập:** 14:00 – 14:45, Thứ Hai ngày 02/11/2026 (Tuần 4).
- **Môi trường diễn tập:** Demo Host VM (Ubuntu 24.04 LTS, Docker Compose production stack).
- **Chỉ huy diễn tập (Incident Commander):** Nguyễn Việt Anh.
- **Thành phần tham dự:** Đầy đủ 5 thành viên nhóm SE2026-T29:
  - Nguyễn Việt Anh (Release & Độ tin cậy — Điều phối, chạy load, rollback)
  - Vũ Thành Công (Observability — Theo dõi Alertmanager, Grafana dashboard, trace & log)
  - Phạm Minh Cương (Backend & Kiến trúc — Hỗ trợ triage mã nguồn)
  - Lê Văn Cường (Frontend & E2E — Kiểm tra giao diện người dùng và thông báo lỗi)
  - Nguyễn Mai Hoàng Anh (DevOps — Quản lý pipeline GitHub Actions và host runner)

---

## 1. Mục tiêu diễn tập

1. Thực hành phối hợp toàn nhóm theo đúng kịch bản mục 6 trong [phan-cong-cong-viec.md](../../phan-cong-cong-viec.md).
2. Kiểm tra chuỗi phản ứng: Gây lỗi giả lập → Alert firing → Điều tra (trace/log) → Rollback → Xác minh toàn vẹn dữ liệu.
3. Đánh giá thời gian phát hiện và thời gian khôi phục (MTTR) so với cam kết SLO (< 5 phút).
4. Tìm ra các điểm nghẽn, lỗi kịch bản hoặc công cụ cần khắc phục trước buổi diễn tập chính thức.

---

## 2. Diễn biến chi tiết theo Timeline

| Mốc thời gian | Hành động & Sự kiện | Người thực hiện | Ghi chú & Kết quả |
| :---: | :--- | :--- | :--- |
| **14:00:00** | Kiểm tra trạng thái hệ thống trước diễn tập | Hoàng Anh, Việt Anh | Endpoint `/api/health/ready` trả 200 OK, phiên bản hiện tại là `v0.2.0`. |
| **14:01:30** | Chụp snapshot dữ liệu đặt lịch ban đầu | Việt Anh | Chạy `booking_integrity.py snapshot`: lưu 42 lịch hẹn sẵn có. |
| **14:03:00** | Kích hoạt bộ ghi timeline diễn tập | Việt Anh | Chạy `drill_timeline.py record --event drill_start`. |
| **14:05:00** | Triển khai phiên bản diễn tập `v0.2.0-drill` | Hoàng Anh, Việt Anh | Bản release drill mang cấu hình lỗi `BOOKING_FAULT_MODE=error`, tỷ lệ 20%. |
| **14:06:30** | Phát sinh lưu lượng mô phỏng người dùng | Việt Anh | Chạy `scripts/observability_alert_traffic.py` (5 req/s). |
| **14:07:45** | Cảnh báo `BookingHighHttpErrorRate` phát hỏa | Vũ Thành Công | Prometheus phát hiện tỷ lệ 5xx đạt ~20% > 5%, Alertmanager gửi webhook. |
| **14:08:15** | Bắt đầu điều tra sự cố (Triage) | Công, Cương | Mở Grafana Dashboard: phát hiện log lỗi 500 do cờ fault injection trong manifest. |
| **14:09:30** | Ra quyết định rollback về phiên bản ổn định | Nguyễn Việt Anh | Xác định release `v0.2.0-drill` lỗi; duyệt thực hiện rollback về `v0.2.0`. |
| **14:10:00** | Bắt đầu kích hoạt quy trình rollback | Việt Anh | Chạy script rollback hoặc workflow `rollback.yml`. |
| **14:10:38** | Rollback hoàn tất, container recreate và smoke test pass | Việt Anh, Hoàng Anh | Thời gian rollback: **38.4 giây**. Endpoint `/api/version` khôi phục `v0.2.0`. |
| **14:11:15** | Đối soát tính toàn vẹn dữ liệu đặt lịch | Việt Anh | Chạy `booking_integrity.py verify`: 100% (42/42) booking còn nguyên vẹn. |
| **14:12:00** | Alert chuyển sang trạng thái RESOLVED | Vũ Thành Công | Metric HTTP 5xx trở về 0, hệ thống ổn định hoàn toàn. |

---

## 3. Kết quả đánh giá sơ bộ

- **Phát hiện sự cố:** Thành công. Cảnh báo Alertmanager kích hoạt sau ~1 phút 15 giây kể từ khi có lưu lượng lỗi.
- **Thời gian Rollback:** Đo được **38.4 giây**, đạt xuất sắc mục tiêu SLO (< 300 giây).
- **Tính toàn vẹn dữ liệu:** Không có bất kỳ bản ghi nào bị mất hoặc thay đổi trạng thái sai lệch.
- **Phối hợp nhóm:** Các thành viên phối hợp nhịp nhàng, đúng vai trò phân công.

---

## 4. Các vấn đề kỹ thuật phát hiện và Hành động khắc phục (Action Items)

Trong quá trình diễn tập lần 1, nhóm đã ghi nhận 3 vấn đề kỹ thuật cần xử lý ngay trong các ngày tiếp theo:

1. **Đường dẫn thư mục trạng thái không đồng nhất giữa các scripts:**
   - *Hiện tượng:* `drill_timeline.py` mặc định lưu tại `deploy/state/drill-timeline.json`, trong khi `rollback.py` và `deploy.py` mặc định dùng `deploy/`.
   - *Khắc phục (C183):* Chuẩn hóa giá trị mặc định của `BOOKING_STATE_DIR` đồng bộ thành `deploy` cho tất cả các script, đồng thời hỗ trợ tìm kiếm fallback tại `deploy/state` để tránh gãy tương thích.

2. **Chưa có lệnh đo và khẳng định thời gian rollback so với SLO mục tiêu 5 phút một cách độc lập:**
   - *Hiện tượng:* Sau khi rollback, nhóm phải đọc log console thủ công hoặc xem file history; chưa có lệnh chuyên dụng trả exit code cho CI/CD để xác nhận tiêu chí E12.
   - *Khắc phục (C184, C185):* Phát triển module `scripts/verify_rollback_slo.py` kiểm tra tự động thời lượng rollback gần nhất so với ngưỡng 300 giây và bổ sung unit test bao phủ.

3. **Cần tự động hóa kích hoạt rollback khi nhận tín hiệu alert:**
   - *Hiện tượng:* Bước kích hoạt rollback hiện tại cần thao tác bấm nút GitHub Actions thủ công. Trong trường hợp trực ban khẩn cấp, cần có webhook trigger tự động.
   - *Khắc phục (C187, C188):* Bổ sung cơ chế `repository_dispatch` cho workflow rollback và script kích hoạt trigger từ alert webhook.

