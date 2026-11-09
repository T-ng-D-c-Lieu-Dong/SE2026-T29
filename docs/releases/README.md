# Releases — Quản lý Phiên bản và Triển khai

Thư mục này chứa tài liệu và quy định liên quan đến quy trình phát hành (release), triển khai (deploy), tương thích cơ sở dữ liệu và khôi phục sự cố (rollback) của hệ thống Booking Service.

## Tài liệu trong mục này

- [Quy trình Release và Deploy (release-process.md)](release-process.md): Hướng dẫn chi tiết về cấu trúc manifest, cấu hình `BOOKING_STATE_DIR`, luồng deploy/rollback, và tệp kiểm toán lịch sử `history.json`.
- [Chính sách Migration tương thích Rollback (migration-policy.md)](migration-policy.md): Nguyên tắc thiết kế schema theo mô hình Expand / Contract, đảm bảo an toàn dữ liệu trong cửa sổ rollback.
- [Manifest tham chiếu v0.1.0 (v0.1.0.json)](v0.1.0.json): Tệp release manifest mẫu cho phiên bản v0.1.0.
- [Release drill và fault config](drill-release.md): Workflow k6 trên demo, fault có thời hạn
  trong manifest, duyệt deploy và khôi phục cấu hình khi rollback.
