# Quy định Migration tương thích với cửa sổ Rollback (E14)

- **Người phụ trách**: Nguyễn Việt Anh (TASK-005 / M4)
- **Áp dụng**: Toàn bộ database migrations bằng Alembic trong repository.
- **Tiêu chuẩn kiểm chứng**: [Evidence E14](../evidence.md) — Release tương thích schema cũ.

---

## 1. Mục tiêu và bối cảnh

Trong kiến trúc single-VM (ADR-001) và quy trình deploy/rollback, cơ chế rollback ứng dụng khôi phục container image và biến môi trường về release manifest trước đó. Khi rollback xảy ra:

1. **Volume PostgreSQL được giữ nguyên** nhằm bảo vệ dữ liệu đặt lịch đã tạo (E12, E13).
2. Database schema **không tự động rollback** (`alembic downgrade` tự động trong sự cố rủi ro gây mất dữ liệu của các giao dịch vừa phát sinh).
3. Do đó, **schema mới sau khi `alembic upgrade head` bắt buộc phải tương thích ngược (backward compatible) với mã nguồn của release trước đó**.

---

## 2. Quy tắc Expand / Contract (Mở rộng trước, thu gọn sau)

Mọi thay đổi cấu trúc bảng `appointments` hoặc các bảng mới phải tuân theo 2 giai đoạn:

### Giai đoạn 1: Expand (Trong release mới)
- **Thêm cột mới**: Bắt buộc phải là `nullable=True` hoặc có `server_default`. Không được tạo cột `NOT NULL` thiếu default.
- **Thêm bảng mới**: Hoàn toàn an toàn vì code cũ không truy vấn đến bảng mới.
- **Thêm index**: Cho phép thêm index hoặc partial index mới miễn là không chặn các thao tác INSERT hợp lệ của code cũ.
- **Không bao giờ**: Đổi tên cột, xóa cột, đổi kiểu dữ liệu gây thu hẹp, hoặc siết chặt constraint của dữ liệu mà code cũ ghi.

### Giai đoạn 2: Contract (Release sau, khi đã đóng cửa sổ rollback)
- Chỉ tiến hành xóa cột cũ hoặc siết constraint `NOT NULL` ở release tiếp theo, sau khi phiên bản mới đã chạy ổn định và vượt qua thời hạn rollback an toàn (tối thiểu 48 giờ sau release).

---

## 3. Bảng kiểm tra trước khi merge migration (Checklist)

| Nội dung kiểm tra | Đạt yêu cầu | Không đạt (phải sửa) |
| --- | --- | --- |
| Cột mới | `sa.Column('note', sa.Text(), nullable=True)` | `sa.Column('note', sa.Text(), nullable=False)` (thiếu default) |
| Xóa cột | Giữ nguyên cột cũ, đánh dấu deprecated trong model | Xóa cột bằng `op.drop_column` ngay trong release đầu |
| Đổi tên cột | Thêm cột mới, sync dữ liệu, giữ cột cũ | Dùng `op.alter_column(..., new_column_name=...)` ngay |
| Constraints | Giữ partial unique index hiện hành | Tạo unique constraint chặn các câu INSERT của release cũ |

---

## 4. Kiểm chứng tự động (E14)

Để đảm bảo mã nguồn phiên bản rollback hoạt động tốt trên database sau migration, repository tích hợp integration test [test_release_e08_e12_e14.py](../../backend/tests/integration/test_release_e08_e12_e14.py):
- Kiểm tra toàn bộ luồng: Xem slot -> Đặt lịch (`201`) -> Xem danh sách (`200`) -> Hủy lịch (`204`).
- Xác nhận code hiện tại tạo/xem/hủy được trên schema test hiện tại. Fixture dùng model
  `Base.metadata.create_all`; test không tự checkout/build image phiên bản cũ hoặc nâng cấp một
  schema cũ bằng Alembic. Vì vậy test này là kiểm tra lifecycle, chưa tự chứng minh tương thích
  giữa hai release khác nhau.

Khi có migration mới, E14 cần thêm một lần kiểm chứng với **hai artifact cụ thể**: tạo dữ liệu
bằng release trước, chạy Alembic upgrade bằng release mới, rồi chạy lại tạo/xem/hủy bằng image
rollback trên chính DB đã nâng cấp. Lưu release/SHA/digest, Alembic revision và kết quả nghiệp vụ;
không chạy downgrade hoặc xóa volume để làm test pass.

## 5. Review schema hiện tại của backend

Ngày 25/10/2026, Phạm Minh Cương (23001840) đối chiếu migration `20261007_0001` với model,
repository và code đã bàn giao. Hiện chỉ có migration khởi tạo; fault injection, request logging
và OpenTelemetry không thêm/đổi/xóa cột hoặc index. Không cần migration mới cho phần việc này.
Chi tiết và giới hạn E14: [Architecture review](../evidence/2026-10-25-architecture-review.md).
