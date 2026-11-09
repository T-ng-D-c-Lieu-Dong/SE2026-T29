# MA TRẬN TRUY VẾT (TRACEABILITY MATRIX) & NHẬT KÝ SỬ DỤNG AI (AI USAGE LOG)
**Bài tập cá nhân 3 — VT-116 | Production Readiness Lab (APP-03)**
- **Sinh viên thực hiện**: Nguyễn Việt Anh (MSSV: 23001827)
- **Nhóm**: SE2026-T29
- **Working Branch**: `bt3/23001827-vt116-soft-delete-restore`

---

## 1. MA TRẬN TRUY VẾT YÊU CẦU & KIỂM THỬ (TRACEABILITY MATRIX)

| Mã Yêu cầu / Rủi ro | Test Case ID | Cấp độ | File Kiểm thử | Git Commit | Bằng chứng Thực thi | Trạng thái |
|---|---|---|---|---|---|---|
| **AC-01** (Soft Delete & Slot Release) | `test_tc01_soft_delete_happy_path` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-02** (Restore to Active Slot) | `test_tc02_restore_happy_path` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-03** / **INV-01** (Slot Conflict Prevention) | `test_tc10_restore_slot_conflict_returns_409` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-04** / **RISK-01** (Cross-User Soft Delete) | `test_tc06_cross_user_soft_delete_forbidden` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-04** / **RISK-01** (Cross-User Restore) | `test_tc07_cross_user_restore_forbidden` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-04** / **RISK-01** (Anti-enumeration Read) | `test_tc08_cross_user_get_detail_isolation` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-05** (Trash API Isolation) | `test_tc09_trash_api_isolation` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **AC-06** (Idempotency Soft Delete & Restore) | `test_tc04_tc05_idempotency_soft_delete_and_restore` | Integration | `backend/tests/integration/test_soft_delete_restore_api.py` | `b417dc9`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **RISK-01** (Authentication Enforcement) | `test_auth_missing_header_returns_401` | Security | `backend/tests/integration/test_soft_delete_restore_api.py` | `06cd0b4`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **RISK-01** (Residual Risk Header Spoofing) | `test_auth_header_spoofing_limitation_demonstration` | Security | `backend/tests/integration/test_soft_delete_restore_api.py` | `06cd0b4`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **INV-01** (Race Condition Concurrency Restores) | `test_concurrent_restore_same_slot_race_condition` | Concurrency | `backend/tests/integration/test_soft_delete_restore_api.py` | `06cd0b4`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **INV-01** (Race Condition Booking + Restore) | `test_concurrent_booking_and_restore_same_slot` | Concurrency | `backend/tests/integration/test_soft_delete_restore_api.py` | `06cd0b4`, `4c6c9b2` | `02-green-test.log` | **VERIFIED** |
| **NFC-01** (40 Concurrency, p95 ≤ 1.5s) | Load test 200 tasks in-flight | Load Test | `scripts/loadtest_vt116.py` | `4c6c9b2` | `04-performance.log`, `.json` | **VERIFIED (p95=0.48s)** |
| **MUTATION** (Deliberate Condition Inversion) | Invert `owner == caller_id` | Mutation | `app/services/booking.py` | Branch tạm thời | `03-mutation.log` | **VERIFIED (KILLED)** |

---

## 2. NHẬT KÝ SỬ DỤNG VÀ HỢP TÁC VỚI AI (AI USAGE LOG)

- **Môi trường & Công cụ AI**: Google Antigravity IDE (Pair-programming Assistant).
- **Quy trình tương tác thực tế**:
  1. *Khảo sát & Lập kế hoạch*: AI quét source code và lập giả định. AI ban đầu đề xuất gán `status = 'cancelled'` làm soft delete và giả định hệ thống đã có auth table.
  2. *Phản biện Checkpoint 1*: Sinh viên Nguyễn Việt Anh trực tiếp bác bỏ 2 giả định của AI:
     - Bác bỏ Giả định A: Yêu cầu Soft Delete phải giải phóng slot, cho phép người khác đặt; khi restore phải kiểm tra xung đột slot và trả 409 Conflict.
     - Bác bỏ Giả định B: Yêu cầu ẩn hoàn toàn bản ghi đã xóa khỏi API đọc thông thường (`404 Not Found`), chỉ cho phép xem qua endpoint thùng rác riêng có xác thực.
  3. *Triển khai Test-First (RED → GREEN)*: AI sinh test trước (12 tests FAILED do thiếu tính năng, commit `67d7fb7`), sau đó tạo patch tối thiểu trên Model, Migration, Repository, Service và API (92 tests PASS, commit `b417dc9`).
  4. *Phản biện Checkpoint 2*: Sinh viên tiếp tục chỉ ra 3 lỗ hổng bảo mật nghiêm trọng trong patch ban đầu:
     - Lỗ hổng gán `owner_id = 'anonymous'` hoặc `customer_name` có thể bị chiếm đoạt do trùng tên.
     - Thiếu xác thực danh tính bắt buộc khi gọi thao tác xóa mềm/khôi phục.
     - Nguy cơ crash 500 do unhandled `IntegrityError` khi có race condition đồng thời ở tầng DB.
  5. *Vá lỗi & Hoàn thiện*: AI khắc phục triệt để: bọc rollback bắt `IntegrityError`, bổ sung `401 Unauthorized` khi thiếu auth, gán `legacy_` unguessable ID cho dữ liệu cũ, chuẩn hóa Ruff/Pyright (commit `06cd0b4`, `4c6c9b2`), và chạy kiểm chứng 40 concurrency p95 đạt 0.48s.

---

## 3. PHÂN TÍCH ĐỘ TIN CẬY CỦA AI (AI RELIABILITY ANALYSIS)

### Điểm 1: AI nhầm lẫn giữa Business Cancellation và Soft Delete
- *Hiện tượng*: AI ban đầu lập luận rằng vì hệ thống đã có `DELETE /api/appointments/{id}` chuyển `status = 'cancelled'` mà không xóa cứng DB, nên có thể tái sử dụng ngay trạng thái này làm xóa mềm.
- *Nguy cơ tiềm ẩn*: Phá vỡ mô hình nghiệp vụ domain. Cancellation là trạng thái nghiệp vụ (khách hủy hẹn, slot giải phóng nhưng lịch sử vẫn hiển thị cho khách xem). Soft delete là thao tác kỹ thuật đưa vào thùng rác (ẩn hoàn toàn khỏi màn hình người dùng). Nếu đánh đồng hai khái niệm, hệ thống không thể phân biệt được một lịch bị hủy với một lịch bị xóa vào thùng rác.
- *Phát hiện & Sửa đổi*: Phản biện của sinh viên tại Checkpoint 1 và đối chiếu partial unique index `uq_appointments_active_starts_at` đã buộc AI phải tách biệt trường `status` và `is_deleted`.

### Điểm 2: AI tin tưởng ngây thơ vào `customer_name` và `X-User-Id`
- *Hiện tượng*: Khi giải quyết phân quyền, AI đề xuất gán `owner_id = customer_name` nếu thiếu header, và cho rằng chỉ cần kiểm tra header không rỗng là đã "xác thực" được danh tính.
- *Nguy cơ tiềm ẩn*: Hai khách hàng trùng tên có thể đọc và xóa lịch của nhau; kẻ tấn công có thể dễ dàng spoofing header `X-User-Id` để mạo danh bất kỳ user nào trong hệ thống.
- *Phát hiện & Sửa đổi*: Sinh viên tại Checkpoint 2 đã bác bỏ kết luận này. AI đã hiệu chỉnh: Dữ liệu cũ trong migration được gán `legacy_` unguessable ID; đồng thời thừa nhận rõ ràng trong báo cáo rằng việc chống spoofing bắt buộc phải dựa vào API Gateway / JWT verification ở mạng biên, đây là Residual Risk của phạm vi backend đơn lẻ.

---
