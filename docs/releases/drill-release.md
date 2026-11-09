# Release drill và khôi phục fault config

Người phụ trách: Nguyễn Việt Anh — TASK-005/TASK-007.

## Cấu hình trong manifest

Manifest có trường `fault` tùy chọn. Manifest cũ không có trường này được hiểu là `mode=off`.
Release thường cũng ghi rõ `BOOKING_FAULT_MODE=off` và `BOOKING_FAULT_UNTIL=` vào env,
để không giữ lại fault của lần deploy trước.

```json
{
  "mode": "error",
  "rate": 0.2,
  "duration_seconds": 900,
  "latency_seconds": 3.0
}
```

`mode` nhận `off`, `error`, `latency`; `rate` từ 0 đến 1; `latency_seconds` từ 0 đến 30.
Fault đang bật cần `duration_seconds` từ 1 đến 3600, hoặc `until` là timestamp có UTC offset.
Giá trị sai bị từ chối khi tạo/load manifest, trước khi ghi env.

Khi dùng `duration_seconds`, deploy tính `until` sau bước duyệt environment, lúc chuẩn bị env.
Manifest release trong GitHub mô tả thời lượng dự kiến; `current-manifest.json` trong state
ghi thêm deadline thực tế. Thời gian chờ **Waiting** không làm hết thời lượng drill.
Khi dùng `until` trực tiếp, deadline là tuyệt đối, không tự gia hạn lúc deploy hay rollback.

## Tạo release drill qua pipeline

1. Merge các thay đổi workflow/scripts vào `main` trước khi tạo tag.
2. Review [deploy/drill-fault.json](../../deploy/drill-fault.json): mặc định gây 500 ở 20% lượt
   đặt trong 15 phút. Có thể đổi mode/rate/thời lượng trong commit trước khi gắn tag.
3. Người phụ trách release push tag `v0.2.0-drill` theo quy trình release của nhóm.
4. `release.yml` chọn file cấu hình trên cho tag kết thúc `-drill` hoặc có hậu tố `-drill.*`,
   truyền `--fault-config` khi tạo manifest. Các tag thường không bật fault.
5. Review artifact manifest, tag/SHA/digest, rồi reviewer khác người push tag duyệt
   **Deploy to Demo Host → Review deployments → Approve**.
6. Deploy chạy migration bằng image release qua Compose profile `migrate`, ghi image refs,
   release/SHA và bốn biến `BOOKING_FAULT_*` vào `/opt/booking/state/.env.production`.

Smoke của drill còn hiệu lực chỉ kiểm tra readiness và release/SHA: lỗi nghiệp vụ là chủ ý
để k6/alert quan sát được, không tự rollback chỉ vì lượt đặt smoke gặp fault.
Readiness/version sai vẫn làm deploy thất bại và kích hoạt rollback như trước.
Release thường, fault hết hạn hoặc rate bằng 0 vẫn chạy đủ smoke nghiệp vụ.

## Rollback và evidence

- Chạy **Rollback Deployment**, để trống target để dùng
  `/opt/booking/state/previous-manifest.json` của lần deploy tốt trước đó.
- Rollback phục hồi image frontend/backend và toàn bộ fault config của manifest đích.
  Manifest đích thường/cũ tắt fault rõ ràng; deadline đã ghi không được gia hạn.
  Manifest fault chỉ có duration, chưa có deadline kích hoạt, không dùng làm đích rollback.
- Rollback không chạy migration; volume PostgreSQL giữ nguyên theo
  [migration-policy.md](migration-policy.md). Smoke rollback luôn kiểm tra nghiệp vụ.
- Artifact deploy/rollback hiện có chứa log, current/previous manifest và `history.json`.
  Dùng deadline trong manifest và timestamp/duration trong history để đối chiếu E12;
  bổ sung kiểm tra booking cũ còn nguyên và link run thật trước khi xác nhận demo đạt.

## k6 trên máy demo

**Actions → Load Test on Demo Host → Run workflow**, chọn `main`, duration `10m`, RPS `10`,
ngày thử riêng và mô tả dataset. Workflow chỉ kích hoạt bằng `workflow_dispatch`, chạy trên
`[self-hosted, demo]`, gọi `http://localhost` qua web port 80. Backend/DB không mở port ra host.

Workflow dùng Docker k6 2.3.0 với host networking, nên không cần cài k6 trên runner.
Artifact `loadtest-demo-<run>-<attempt>` luôn được upload, kể cả khi thresholds thất bại:
summary JSON, log k6, version API, thông tin CPU/RAM/OS/Docker và manifest/history hiện tại.
Test có fault dự kiến có thể exit 99; đọc artifact để đối chiếu tỷ lệ lỗi và thời điểm fault.
Phép đo E15 chạy riêng ở release tốt, đủ 10 phút và đúng tải thực tế.

Một runner chỉ chạy một job tại một thời điểm. Workflow k6 10 phút chiếm runner đó;
không dùng nó đồng thời với drill cần rollback trong 5 phút trên cùng một runner.
Để diễn tập có rollback khi tải còn chạy, chạy k6 từ terminal trên máy tạo tải
(gọi URL máy demo), hoặc bố trí runner khác. Tham khảo [loadtest/README.md](../../loadtest/README.md).

## Kiểm tra cục bộ

Unit tests kiểm tra schema, thời hạn, env tương thích backend, lưu manifest khi deploy,
rollback về `off`, và smoke drill vẫn bắt sai version. Compose config đã được đối chiếu
với env sinh ra; actionlint kiểm tra tất cả workflows.
Kết quả ngày 27/10/2026: **121 unit tests pass**, Ruff check/format và actionlint đạt;
đảo điều kiện hết hạn làm regression test thất bại đúng dự kiến, sau đó đã khôi phục mã.
Các kiểm tra này chưa thay thế lần chạy GitHub Actions và fault drill trên máy demo.
