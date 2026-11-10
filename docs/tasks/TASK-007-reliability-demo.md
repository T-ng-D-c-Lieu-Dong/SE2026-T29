# TASK-007 — Reliability demo và evidence

- Trạng thái: **In Progress**
- Người phụ trách: **Nguyễn Việt Anh (23001827)**
- Mốc: **M6 — Reliability demo**
- Phụ thuộc: TASK-005, TASK-006

## Mục tiêu

Chạy thử tải và incident drill để chứng minh khả năng phát hiện, điều tra và khôi phục hệ thống.

## Công việc

- Chuẩn bị load script và fault injection có thời hạn trên môi trường demo.
- Chạy tải tham chiếu 10 request/giây trong 10 phút và lưu điều kiện đo.
- Ghi timeline fault, alert, điều tra, rollback và phục hồi nghiệp vụ.
- Kiểm tra booking cũ còn nguyên sau rollback.
- Lưu test results, telemetry queries, release manifest và incident report.
- Cập nhật trạng thái E01–E16 bằng bằng chứng thực tế.

## Tiêu chí hoàn thành

- Báo cáo độ trễ ghi rõ môi trường, dữ liệu, phiên bản và khoảng đo.
- Alert firing trong mục tiêu đã định; tìm được trace/log và release gây lỗi.
- Rollback hoàn tất trong mục tiêu 5 phút, smoke test pass và dữ liệu còn nguyên.
- Incident report và toàn bộ link evidence cần thiết đã được lưu.
- Không mô tả hệ thống là “production-ready” nếu chưa đủ bằng chứng.

## Tiến độ tuần 2 — thứ Hai và thứ Ba (C081–C084)

- Hoàn thành luồng xem slot → đặt → hủy trong `loadtest/booking.js`; tách riêng `409`.
- Có profile mặc định 10 HTTP request/giây trong 10 phút, ngưỡng p95 < 500 ms
  cho từng route, lỗi < 1%, kiểm tra dropped iterations và các checks nghiệp vụ.
- Tự xuất summary JSON kèm cấu hình tải, release/SHA và điều kiện đo;
  hướng dẫn chạy tại [loadtest/README.md](../../loadtest/README.md).
- [Kiểm tra script ngày 27/10/2026](../evidence/loadtest/2026-10-27-week2-smoke.md):
  22 kiểm thử JavaScript, 85 unit tests, k6 inspect và smoke với PostgreSQL/API thật.
- **E15 vẫn chưa kiểm chứng**: smoke 15 giây chỉ xác nhận script hoạt động;
  phép đo 10 phút trên môi trường tham chiếu và incident drill còn lại trong TASK-007.

## Phối hợp sau PR #26

- C085: có workflow k6 chỉ chạy thủ công trên `[self-hosted, demo]`, branch `main`,
  gọi web port 80; luôn lưu artifact summary/log/version/cấu hình máy/manifest/history.
- C088–C089: manifest mang fault config, deploy ghi deadline kích hoạt và rollback về
  release thường tắt fault rõ ràng; có regression tests cho phục hồi cấu hình.
- Tag `*-drill` lấy cấu hình tại `deploy/drill-fault.json`; migration tiếp tục dùng
  image release qua Compose profile `migrate`. Rollback không chạy migration.
- [Hướng dẫn chạy và evidence](../releases/drill-release.md).
- Chưa chạy workflow mới trên máy demo; chưa tạo/push tag drill hoặc duyệt deployment.

## Đối chiếu công việc thứ Tư và thứ Năm (C085–C088)

- C086–C087 đã có từ commit `3df685d`: smoke test đối chiếu release và commit SHA từ
  manifest với `/api/version`; deploy và rollback đều truyền giá trị của manifest đích.
  Bộ kiểm thử có trường hợp đúng và sai release; bổ sung kiểm thử sai commit SHA.
- C085 và C088 đã hoàn thành phần mã tại `2e48e1b` và `8e4b6d7`. Việc chạy workflow
  và kiểm chứng rollback trên máy demo vẫn cần thực hiện để có evidence thực tế.

## Đối chiếu tuần 2 ngày 28/10/2026

- C081–C090 đã hoàn thành ở mức code/test/tài liệu; smoke version check và rollback runbook vốn đã
  có từ TASK-005, nay được liên kết lại đúng commit trong lịch.
- TASK-007 vẫn `In Progress`: chưa chạy E15 đủ 10 phút, incident timeline và rollback drill thật
  trên demo host. Xem [bảng đối chiếu](../evidence/2026-10-28-week2-reconciliation.md).
