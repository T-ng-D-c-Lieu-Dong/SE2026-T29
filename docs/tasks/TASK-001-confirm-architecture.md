# TASK-001 — Xác nhận kiến trúc

- Trạng thái: **Done** — phần chốt thiết kế; thay đổi được bàn giao qua pull request.
- Người phụ trách: **Phạm Minh Cương (23001840)**
- Mốc: **M0 — Architecture**
- Phụ thuộc: Không

## Mục tiêu

Thống nhất phạm vi, giả định, các view kiến trúc và quyết định triển khai trước khi viết ứng dụng.

## Công việc

- Team review [architecture context](../architecture/architecture-context.md), module view và runtime view.
- Xác nhận quy tắc booking, timezone, phạm vi MVP và các mục tiêu chất lượng.
- Chấp nhận hoặc sửa [ADR-001](../architecture/adr/001-use-docker-compose.md).
- Phân công owner cho các task còn lại.

## Tiêu chí hoàn thành

- Các giả định quan trọng đã được team xác nhận và cập nhật trong tài liệu.
- Module view và runtime view phù hợp với hướng triển khai đã thống nhất.
- ADR-001 chuyển từ `Proposed` sang `Accepted`, hoặc có ADR thay thế.
- Bảng backlog có owner cho các task sẽ bắt đầu.

## Kết quả ngày 25/10/2026

- Đối chiếu context, module view và runtime view với code trên `main` tại `fa8422f`.
- Chốt MVP: lịch dùng chung, slot 30 phút, thời gian có offset và chuẩn hóa UTC, chống trùng tại
  PostgreSQL, hủy giữ lịch sử; chỉ dùng dữ liệu demo khi chưa có tài khoản/phân quyền.
- ADR-001 chuyển sang `Accepted`, Phạm Minh Cương chịu trách nhiệm lựa chọn kiến trúc.
- Cập nhật đường dẫn frontend, observability, tests và luồng migration theo repository thực tế;
  tách trạng thái local khỏi phần production/demo còn phải triển khai.
- Review migration đầu tiên và quy tắc expand/contract; không cần migration mới cho fault/log/OTel.
- Kết quả chi tiết và các việc bàn giao: [Architecture review](../evidence/2026-10-25-architecture-review.md).

Quyết định của người phụ trách được ghi theo yêu cầu chốt TASK-001. Tài liệu này không thay cho
approval của thành viên khác trên GitHub hoặc một biên bản họp nhóm chưa diễn ra. TASK-007 cần
được nhóm xác nhận người phụ trách trước khi bắt đầu drill chung.
