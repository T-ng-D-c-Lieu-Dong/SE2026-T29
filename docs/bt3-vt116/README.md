# BÀI TẬP CÁ NHÂN 3 — BIẾN THỂ VT-116
## APP-03: Production Readiness Lab
**Sinh viên:** Nguyễn Việt Anh  
**MSSV:** 23001827  
**Nhóm:** SE2026-T29 (Vai trò: QA Automation & Backend Engineer)  
**Branch thực thi:** `bt3/23001827-vt116-soft-delete-restore`  
**Baseline Commit:** `8fe9de89b719bde237a118e18a671db1d3dfd6cd` (origin/main)  

---

## 1. Giới thiệu & Phạm vi Triển khai

Biến thể **VT-116** yêu cầu mở rộng Backend hệ thống đặt lịch khám bệnh với chức năng:
- **Xóa mềm (Soft Delete)** và **Khôi phục (Restore)** lịch hẹn.
- **Tính nhất quán dữ liệu liên quan:** Khi soft delete, slot thời gian phải được giải phóng cho người dùng khác đặt. Khi restore, nếu slot đã bị chiếm thì hệ thống từ chối (`409 Conflict`), không ghi đè lịch hiện hữu.
- **Bảo mật & Phân quyền (RISK-01):** Ngăn chặn người dùng đọc, xóa mềm, khôi phục lịch hẹn của người khác (Cross-user unauthorized access/mutation). Lịch đã xóa mềm bị ẩn hoàn toàn khỏi API công khai (`GET /api/appointments/{id}` trả về `404 Not Found` chống ID enumeration), chỉ có thể truy vấn qua API thùng rác riêng `/api/appointments/trash` có xác thực quyền sở hữu.
- **Kiểm thử chuyển trạng thái (State Transition Testing):** Thiết kế ma trận 8 trạng thái/chuyển dịch phủ kín lifecycle của cuộc hẹn.
- **Thực nghiệm Mutation:** Đảo điều kiện `owner != caller_id` thành `owner == caller_id` trong business rule để kiểm chứng năng lực phát hiện lỗi của test suite (100% mutation killed).
- **Thực nghiệm Hiệu năng:** Đo lường 40 người dùng đồng thời, p95 đạt 482.7 ms (ràng buộc đề bài: $\le 1.5$ s).

---

## 2. Cấu trúc Tài liệu & Evidence

Thư mục `docs/bt3-vt116/` bao gồm:
- `repository-audit.md`: Khảo sát kiến trúc hiện hữu, baseline verification và phân tích rủi ro ban đầu.
- `implementation-plan.md`: Kế hoạch triển khai chi tiết, ghi nhận 4 assumptions và 2 điểm phản biện của sinh viên tại Checkpoint 1 & 2.
- `test-strategy.md`: Chiến lược kiểm thử State Transition, ma trận chuyển dịch và danh sách test cases.
- `traceability-and-ai-log.md`: Ma trận truy vết (Traceability Matrix) từ Change Request $\rightarrow$ Risk $\rightarrow$ Architecture $\rightarrow$ Test $\rightarrow$ Evidence, kèm nhật ký tương tác AI Usage Log.
- `evidence/`: Thư mục lưu trữ log thực nghiệm độc lập:
  - `01-red-test.log`: Minh chứng Test-first RED (12 tests FAILED, 1 test PASS ban đầu).
  - `02-green-test.log`: Minh chứng Test GREEN sau khi implement (96/96 tests PASSED).
  - `03-mutation.log`: Minh chứng Mutation Test (9 tests FAILED lập tức khi đảo logic phân quyền $\rightarrow$ KILLED).
  - `04-performance.log`: Chi tiết thực nghiệm tải 40 tác vụ đồng thời (200 lifecycles, 0 errors, p95 = 482.7 ms).
  - `04-performance.json`: Dữ liệu JSON thô của từng transaction và metrics thống kê.
- `BT3_23001827_VT-116.tex`: Mã nguồn LaTeX báo cáo khoa học 8 trang chính + Phụ lục.
- `BT3_23001827_VT-116.pdf`: Báo cáo PDF chính thức hoàn chỉnh.

---

## 3. Hướng dẫn Tái lập Thực nghiệm (Reproducibility Guide)

### 3.1. Yêu cầu môi trường
- Python $\ge$ 3.11 (đã kiểm thử trên Python 3.14 venv).
- Docker & Docker Compose (cho PostgreSQL test database).

### 3.2. Khởi tạo Cơ sở dữ liệu Test
```bash
# Khởi chạy PostgreSQL test container (chạy trên port 55432)
docker compose -f backend/docker-compose.test.yml up -d
```

### 3.3. Thiết lập Virtual Environment & Cài đặt Dependencies
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3.4. Chạy Toàn bộ Test Suite (96 Tests)
```bash
TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:55432/booking_test" \
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:55432/booking_test" \
pytest tests/ -v
```
*Kết quả kỳ vọng:* 96 passed in ~3.2s.

### 3.5. Tái lập Thực nghiệm Mutation Testing
1. Mở file `backend/app/services/booking.py`, tìm phương thức `soft_delete`:
   ```python
   # Dòng gốc:
   if appointment.owner_id and appointment.owner_id != caller_id:
       raise UnauthorizedAppointmentAccess("Cannot delete appointment owned by another user")
   ```
2. Đảo điều kiện (deliberate mutation):
   ```python
   # Đảo thành:
   if appointment.owner_id and appointment.owner_id == caller_id:
       raise UnauthorizedAppointmentAccess("Cannot delete appointment owned by another user")
   ```
3. Chạy test suite:
   ```bash
   pytest tests/integration/test_soft_delete_restore_api.py -v
   ```
   *Kết quả kỳ vọng:* 9/17 tests FAILED ngay lập tức (Mutation KILLED).
4. Hoàn nguyên code về trạng thái ban đầu (`git checkout backend/app/services/booking.py`).

### 3.6. Tái lập Thực nghiệm Hiệu năng (Load Test 40 Concurrency)
Đảm bảo test database đang chạy, sau đó chạy script từ thư mục gốc repository:
```bash
# Từ thư mục gốc SE2026-T29/
PYTHONPATH=backend backend/.venv/bin/python scripts/loadtest_vt116.py
```
*Kết quả kỳ vọng:*
- 200 lifecycle tasks hoàn tất.
- 0 failures.
- Latency p95 $\approx 450 - 550$ ms (thỏa mãn $\le 1500$ ms).

---

## 4. Tóm tắt Thay đổi Mã nguồn (Git Commits)

| Commit SHA | Loại | Tóm tắt thay đổi |
|:---|:---|:---|
| `67d7fb7` | `test(bt3)` | Thêm test suite cho soft delete và restore (RED phase - 12 tests fail) |
| `b417dc9` | `feat(bt3)` | Triển khai soft delete, restore, ownership authorization và trash API (GREEN phase) |
| `06cd0b4` | `fix(bt3)` | Xử lý phản biện Checkpoint 2: Auth enforcement (401), DB race rollback, legacy ownership migration |
| `4c6c9b2` | `fix(bt3)` | Chuẩn hóa IDE diagnostics, ruff lint, migration isolation và formatting |
| `add1990` | `feat(bt3)` | Bổ sung script load test 40 concurrency, mutation log và ma trận truy vết |

*Lưu ý:* Tất cả thay đổi được cách ly trên branch `bt3/23001827-vt116-soft-delete-restore`, không merge vào `main` để bảo toàn tiến độ nhóm chung.

