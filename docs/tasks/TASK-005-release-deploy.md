# TASK-005 — Release, deploy và rollback

- Trạng thái: **Done**
- Người phụ trách: **Nguyễn Việt Anh (23001827)**
- Mốc: **M4 — Release + Deploy**
- Phụ thuộc: TASK-004

## Mục tiêu

Phát hành image có định danh, triển khai đúng artifact và khôi phục được phiên bản tốt trước đó.

## Công việc

- Tạo release workflow build và push image từ Git tag.
- Tạo release manifest chứa tag, commit SHA, image digests và migration revision.
- Viết deploy và rollback scripts có khóa chống chạy đồng thời.
- Thêm readiness timeout và smoke test nghiệp vụ sau deploy.
- Quy định migration tương thích với cửa sổ rollback.

## Tiêu chí hoàn thành

- `/api/version`, manifest và image đang chạy chỉ cùng một release.
- Deploy dùng image digest, không build lại trên VM và không dùng `latest`.
- Deploy lỗi tự khôi phục manifest trước đó và giữ nguyên booking cũ.
- Kiểm chứng E08, E12 và E14 trong [Evidence](../evidence.md) đạt.

## Kết quả

- Workflows: `.github/workflows/release.yml`, `.github/workflows/rollback.yml`, `.github/workflows/ci.yml`.
- Dockerfile và Compose: `backend/Dockerfile`, `deploy/compose.production.yaml`, `deploy/compose.yaml`.
- Scripts & Tools: `scripts/release_manifest.py`, `scripts/deploy_lock.py`, `scripts/deploy_history.py`, `scripts/smoke_test.py`, `scripts/deploy.py`, `scripts/rollback.py`, `scripts/deploy.sh`, `scripts/rollback.sh`, bộ công cụ load test `loadtest/` (`slots.js`, `booking.js`).
- Tài liệu quy định: [Quy trình Release và Deploy](../releases/release-process.md), [Chính sách Migration](../releases/migration-policy.md), manifest mẫu `docs/releases/v0.1.0.json`, tài liệu load test `loadtest/README.md`.
- Kiểm chứng: 84 unit tests pass 100%, Ruff check & format pass.
- Bằng chứng chi tiết: [Release and Rollback evidence](../evidence/2026-10-14-release-deploy.md).
