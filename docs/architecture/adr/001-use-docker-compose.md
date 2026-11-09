# ADR-001 — Docker Compose trên một Linux VM

- Ngày: 07/10/2026
- Trạng thái: **Accepted** — chốt thiết kế ngày 25/10/2026.
- Phạm vi: môi trường demo của Production Readiness Lab.
- Người chịu trách nhiệm quyết định: **Phạm Minh Cương (23001840)** — backend và kiến trúc.
- Căn cứ chốt: yêu cầu hoàn tất TASK-001 của người phụ trách và [review code/kiến trúc](../../evidence/2026-10-25-architecture-review.md). Review của thành viên khác được ghi qua pull request.

## Context

Project có một frontend, một backend nhỏ, PostgreSQL và các dịch vụ observability. Mục tiêu là trình diễn CI/CD, release có định danh, theo dõi sự cố và rollback. Nghiệp vụ chưa cần nhiều backend hoặc điều phối đa host. Team cần hạn chế thời gian vận hành hạ tầng và chi phí môi trường lab.

## Decision

Dùng Docker Compose để chạy các containers trên một Linux VM. API giữ dạng modular monolith. Tách cấu hình local và cấu hình deployment; pin images theo release manifest/digest. PostgreSQL và telemetry dùng volumes riêng.

CI/CD do GitHub Actions thực hiện. Quy trình deploy/rollback được team viết rõ: lưu manifest, thay image/config, kiểm tra readiness và smoke test, khôi phục manifest trước khi lỗi. Compose là công cụ chạy services; logic release và quyết định rollback thuộc workflow/scripts.

## Alternatives

| Phương án | Lợi ích | Chi phí / giới hạn | Đánh giá trong bối cảnh lab |
| --- | --- | --- | --- |
| Docker Compose trên một VM | Một cấu hình services/networks/volumes; dễ tái tạo và demo | VM là điểm lỗi chung; cần tự xây deploy/rollback và kiểm tra | Chọn |
| Kubernetes | Có orchestration, rolling deployment và cơ chế đa node | Cần cluster, manifests, ingress/storage và thêm kỹ năng vận hành | Cân nhắc khi có yêu cầu nhiều node hoặc HA |
| Cài runtime trực tiếp lên VM | Ít công cụ ban đầu | Dễ lệch dependency; cần quản lý services và đóng gói thủ công | Không phù hợp mục tiêu container hóa của lab |
| Managed platform / PaaS | Giảm công việc quản lý VM | Tính năng, chi phí và quyền cấu hình phụ thuộc nền tảng | Có thể xem lại nếu team ưu tiên vận hành được quản lý |

## Consequences

**Tích cực:** môi trường local và deployment chia sẻ cấu trúc container; thời gian học/tạo hạ tầng thấp hơn mô hình cluster; team tập trung vào evidence về pipeline và recovery.

**Đánh đổi:** một VM không có HA. Deploy/rollback có thể gián đoạn ngắn. Team vẫn quản lý bản vá host, dung lượng đĩa, volumes, backup và retention. Observability chung VM có thể bị ảnh hưởng khi VM lỗi.

**Trách nhiệm phát sinh:** bổ sung readiness và smoke tests; serial hóa deploy; giữ image cũ và manifest; kiểm tra migration tương thích; giới hạn port quản trị; đo CPU/RAM/disk trước drill. Backup/restore DB là quy trình khác với rollback ứng dụng.

## Validation

1. Chạy stack ở môi trường demo, UI đặt và hủy lịch thành công.
2. Tái tạo API container và xác nhận booking còn nguyên.
3. Deploy release drill, nhận alert và đối chiếu trace/log với release.
4. Rollback trong mục tiêu 5 phút, xác nhận đúng version/digest và nghiệp vụ phục hồi.
5. Ghi kết quả, điều kiện máy và giới hạn trong Evidence/Incident report.

Đã có kết quả cục bộ cho UI, telemetry và dữ liệu qua recreate; xem E06, E09–E11, E13 và E16
trong [Evidence](../../evidence.md). Kết quả E12 hiện là kiểm chứng cục bộ/mô phỏng, chưa thay thế
một lần deploy → fault → rollback đầy đủ trên máy demo. E15 và thông báo Discord thật còn thiếu.

`Accepted` xác nhận lựa chọn kiến trúc, không xác nhận đã đạt toàn bộ mục tiêu vận hành.
Production Compose hiện chỉ có API/DB; web container, phát hành frontend theo digest và
deploy/rollback tới máy demo vẫn cần được nhóm hoàn thiện theo runtime view.

## Khi xem lại quyết định

Xem lại khi cần nhiều host, HA, cập nhật không gián đoạn, tài nguyên telemetry vượt một VM hoặc vận hành môi trường công khai cho khách thật. ADR mới sẽ thay thế quyết định này; giữ ADR cũ để lưu lý do ban đầu.

## Tham chiếu

[Docker — Use Compose in production](https://docs.docker.com/compose/how-tos/production/). Lựa chọn và đánh đổi trong ADR là quyết định của project, không phải cam kết HA từ Docker.
