# Kịch bản Trình diễn & Thuyết minh Đồ án trước Hội đồng (Defense Demo Script)

- **Người thuyết trình:** **Nguyễn Việt Anh (23001827)** — Release Engineer & Reliability Lead
- **Thời lượng chuẩn:** **10 phút** (7 phút demo thực tế + 3 phút kết luận & hỏi đáp)
- **Mục tiêu:** Thuyết phục hội đồng chấm điểm bằng số liệu thực tế, dashboard trực quan và khả năng tự khôi phục của hệ thống.

---

## 1. Dòng thời gian trình diễn chi tiết (Minute-by-Minute Timeline)

### Phút 00:00 – 02:00: Mở đầu & Kiến trúc Hệ thống
* **Nói gì:**
  * Giới thiệu bài toán: Booking API & Platform được thiết kế hướng tới **Production Readiness** với trọng tâm là độ tin cậy và tự khôi phục.
  * Chỉ ra các cam kết cốt lõi: Cam kết p95 $< 500\text{ ms}$, phát hiện lỗi $< 3\text{ phút}$, rollback $< 5\text{ phút}$, và bảo toàn $100\%$ dữ liệu.
* **Thao tác màn hình:**
  * Chiếu sơ đồ kiến trúc tổng quan trong `README.md`.
  * Mở terminal gõ: `python3 -m scripts.sre_cli status` để cho thầy thấy trạng thái hệ thống lành và không bị khóa.

### Phút 02:00 – 04:00: Thử tải & Quan sát Hệ thống (Observability Demo)
* **Nói gì:**
  * Hệ thống đang chịu tải người dùng thật bằng k6 với tốc độ 10 requests/giây gồm cả luồng đọc slot, đặt lịch và hủy lịch.
  * Tỷ lệ lỗi 5xx là $0.0\%$, độ trễ p95 đạt mức cực tốt $35.8\text{ ms}$.
* **Thao tác màn hình:**
  * Chạy nhanh k6 test hoặc chiếu Dashboard Grafana thời gian thực: Biểu đồ RPS, HTTP Request Duration, Active Connections.

### Phút 04:00 – 07:00: Cao trào — Tiêm lỗi & Điều tra Sự cố (Incident & RCA)
* **Nói gì:**
  * Giả lập tình huống phát hành một release lỗi (`v0.2.0-drill`) có tỷ lệ lỗi 20% HTTP 500.
  * Quan sát cảnh báo: Sau đúng 78 giây, rule `BookingHighHttpErrorRate` phát hỏa và Alertmanager gửi webhook tới Discord.
  * Điều tra nguồn gốc: Đi từ Alert → Trace ID trên Tempo → Log exception trên Loki, chứng minh lỗi do commit mới gây ra.
* **Thao tác màn hình:**
  * Chiếu thông báo Alert Discord.
  * Mở Grafana Tempo click vào Trace ID lỗi, nhảy sang Loki xem stacktrace.

### Phút 07:00 – 09:00: Khôi phục Khẩn cấp & Đối soát Toàn vẹn (Rollback & Data Integrity)
* **Nói gì:**
  * Incident Commander ra lệnh rollback khẩn cấp về release an toàn `v0.2.1`.
  * Cơ chế Rollback Guard thẩm định tính tương thích schema và dung lượng đĩa trước khi recreate container.
  * Quá trình rollback hoàn tất trong **39,2 giây** (đạt chuẩn SLO $< 300\text{s}$).
  * Chạy đối soát dữ liệu: $100\%$ booking cũ không bị mất mát. Cảnh báo tự động chuyển về `[RESOLVED]`.
* **Thao tác màn hình:**
  * Thực thi lệnh: `python3 -m scripts.rollback --target-manifest docs/releases/v0.2.1.json --verify-slo`
  * Chạy: `python3 -m scripts.booking_integrity verify --baseline deploy/baseline-bookings.json`
  * Cho thầy thấy dòng chữ: `All bookings intact (100% matched)`.

### Phút 09:00 – 10:00: Tổng kết & Trả lời Câu hỏi
* **Nói gì:**
  * Tóm tắt các thành tựu: Toàn bộ 16/16 bằng chứng E01–E16 nghiệm thu thành công.
  * Bài học kinh nghiệm về văn hóa không đổ lỗi (Blameless Culture) và tầm quan trọng của Release Manifest bất biến.
* **Sẵn sàng trả lời các câu hỏi kỹ thuật sâu của thầy về:** Docker volume lifecycle, schema backward compatibility, multi-window error budget burn rate.

