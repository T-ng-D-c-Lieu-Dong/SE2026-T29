# Báo cáo Chuyên đề: Phân tích & So sánh Định lượng Độ tin cậy (Reliability Synthesis)

- **Tác giả:** **Nguyễn Việt Anh (MSSV: 23001827)** — Release Engineer & Reliability Lead
- **Phạm vi:** Đối chiếu kết quả giữa Đợt Diễn tập thử nghiệm (Rehearsal 1 — 02/11/2026) và Đợt Diễn tập chính thức (Official Drill — 23/11/2026) trên máy Demo Host.

---

## 1. Bảng đối chiếu định lượng qua các đợt diễn tập

| Tiêu chí đo lường | Mục tiêu cam kết (SLO) | Diễn tập Thử nghiệm (Rehearsal 1) | Diễn tập Chính thức (Official Drill) | Xu hướng cải thiện |
| :--- | :---: | :---: | :---: | :---: |
| **Thời gian phát hiện (MTTD)** | $< 180\text{ s}$ | $75\text{ giây}$ | **$78\text{ giây}$** | Ổn định trong ngưỡng vàng ($75\text{s} - 78\text{s}$) |
| **Thời gian khôi phục (MTTR)** | $< 300\text{ s}$ | $38,45\text{ giây}$ | **$39,20\text{ giây}$** | Tái lặp tất định, vượt trội so với SLO |
| **Tỷ lệ bảo toàn dữ liệu (RPO)** | $100\%$ | $100\%$ ($10/10$ bookings) | **$100\%$ ($32/32$ bookings)** | Đạt mục tiêu Zero Data Loss |
| **Độ trễ p95 sau khôi phục** | $< 500\text{ ms}$ | $38,2\text{ ms}$ | **$34,2\text{ ms}$** | Giảm $10.4\%$ độ trễ sau warmup |
| **Thời gian đóng cảnh báo** | Tự động | $60\text{ giây}$ sau smoke test | **$31\text{ giây}$ sau smoke test** | Alertmanager nhận resolved nhanh hơn $48\%$ |

---

## 2. Các nhân tố then chốt giúp tối ưu hóa MTTR

1. **Phân vai rõ ràng (Role Discipline):**
   - Sự phối hợp chặt chẽ giữa Incident Commander (Nguyễn Việt Anh) và Operator/Investigator giúp loại bỏ hoàn toàn độ trễ do do dự hoặc trao đổi mơ hồ.
2. **Deterministic Release Manifests:**
   - Việc cố định Docker image bằng SHA-256 digest giúp quá trình kéo image và recreate container không bị phụ thuộc vào cache layer không nhất quán.
3. **Cơ chế Khóa triển khai (Deployment Lock):**
   - Đảm bảo trong suốt quá trình xử lý sự cố, không có job CI/CD nào vô tình trigger đè lên môi trường.

---

## 3. Khuyến nghị kiến trúc khi mở rộng (Future Architecture Scaling)

- **Chuyển dịch sang Multi-Host (Kubernetes / Nomad):** Thay thế single-VM Compose bằng Rolling Update hoặc Canary Deployment trên cụm container đa node để đạt Zero-Downtime thực sự.
- **Persistent Error Budget Engine:** Tích hợp script `calculate_error_budget` thành cronjob định kỳ 5 phút đẩy metric `booking_error_budget_burn_rate` vào Prometheus để hiển thị trực tiếp lên Grafana Alert Dashboard.

