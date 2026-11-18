# Kiến trúc Quản lý SLO & Chính sách Ngân sách Lỗi (SLO & Error Budget Policy)

- **Người phụ trách:** **Nguyễn Việt Anh (23001827)** — Release Engineer & Reliability Lead
- **Áp dụng cho:** Dịch vụ Đặt lịch hẹn (Booking Platform) — SE2026-T29
- **Tiêu chuẩn tham chiếu:** *Google Site Reliability Engineering (SRE) Handbook*

---

## 1. Định nghĩa Chỉ số SLI & Mục tiêu SLO

Hệ thống đặt lịch cam kết các mục tiêu chất lượng dịch vụ (Service Level Objectives) định lượng cụ thể:

| Hạng mục | Chỉ số chất lượng (SLI) | Mục tiêu cam kết (SLO) | Cửa sổ đánh giá |
| :--- | :--- | :---: | :---: |
| **Tính sẵn sàng (Availability)** | $\frac{\text{Số request HTTP } < 500}{\text{Tổng số request hợp lệ}}$ | **$\ge 99.0\%$** | Rolling 30 ngày |
| **Độ trễ phản hồi (Latency)** | Tỷ lệ request hoàn thành dưới $500\text{ ms}$ | **$\ge 95.0\%$** | Rolling 30 ngày |
| **Thời gian phát hiện lỗi (MTTD)** | Thời gian từ khi lỗi xuất hiện đến lúc Alert Firing | **$< 180\text{ giây}$** | Từng sự cố |
| **Thời gian khôi phục (MTTR)** | Thời gian từ lúc quyết định đến khi rollback hoàn tất | **$< 300\text{ giây}$** | Từng sự cố |

---

## 2. Ngân sách Lỗi (Error Budget) & Tốc độ Đốt (Burn Rate)

Với SLO Tính sẵn sàng $99.0\%$, ngân sách lỗi cho phép trong chu kỳ 30 ngày ($720\text{ giờ}$) là **$1.0\%$** tổng số request.

### Công thức tính Burn Rate:
$$\text{Burn Rate} = \frac{\text{Tỷ lệ lỗi thực tế}}{\text{Tỷ lệ lỗi cho phép (1 - SLO)}} = \frac{\text{Error Rate}}{0.01}$$

### Bảng cảnh báo đa cửa sổ (Multi-Window Alerting):

| Mức độ cảnh báo | Ngưỡng Burn Rate | % Ngân sách đốt | Cửa sổ đo | Hành động tự động |
| :---: | :---: | :---: | :---: | :--- |
| **Critical (Page)** | $\ge 14.4\text{x}$ | $2\%$ budget trong $1\text{h}$ | $1\text{ giờ}$ | Đẩy webhook khẩn cấp, kích hoạt auto-rollback |
| **Warning (Ticket)**| $\ge 6.0\text{x}$ | $5\%$ budget trong $6\text{h}$ | $6\text{ giờ}$ | Thông báo kênh Discord, kỹ sư vào rà soát |
| **Nominal (OK)** | $< 1.0\text{x}$ | Hoạt động bình thường | $30\text{ ngày}$ | Cho phép triển khai phiên bản tính năng mới |

Công cụ tính toán tự động:
```bash
python3 -m scripts.calculate_error_budget --total 10000 --errors 50 --window-hours 1.0
```

---

## 3. Chính sách Xử lý khi Hết Ngân sách Lỗi (Error Budget Policy)

Khi Error Budget bị tiêu hao vượt quá $100\%$ trong chu kỳ 30 ngày:
1. **Đóng băng phát hành tính năng mới (Feature Freeze):**
   - Mọi Pull Request bổ sung tính năng nghiệp vụ mới đều bị tạm dừng merge vào nhánh `main`.
2. **Ưu tiên kỹ thuật độ tin cậy:**
   - $100\%$ thời gian của nhóm kỹ sư tập trung vào sửa lỗi gốc rễ (RCA), tối ưu hóa database queries, bổ sung automated tests và củng cố pipeline.
3. **Điều kiện gỡ bỏ đóng băng:**
   - Hệ thống vận hành ổn định liên tục ít nhất 7 ngày không phát sinh vi phạm SLO và ngân sách lỗi bắt đầu hồi phục.

