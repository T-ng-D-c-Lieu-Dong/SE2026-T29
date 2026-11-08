# Frontend — Kiểm chứng nửa đầu tuần 3

- **Ngày:** 01/11/2026
- **Task:** TASK-003 — Lê Văn Cường
- **Phạm vi:** C123, C124, C125, C128, C130 (5/10 đầu việc tuần 3)
- **Nền:** `d2dffaf` (`main` sau PR #28)

## Thay đổi

| Đầu việc | Nội dung | Commit |
| --- | --- | --- |
| C123 | E2E đổi ngày phải gọi lại `/api/slots` với ngày mới và hiển thị đúng số slot API trả về | `791e0ef` |
| C124 | Component test cho phân trang danh sách lịch và nút yêu cầu huỷ | `50cec31` |
| C128 | Test xác nhận slot và danh sách lịch được refetch sau khi đặt thành công | `36907ff` |
| C125, C128 | E2E đặt lịch: slot vừa đặt biến mất khỏi danh sách trống | `2deb17f` |
| C125, C128 | E2E huỷ lịch: slot được trả lại danh sách trống sau khi huỷ | `741bcf3` |
| C125, C128 | Test xác nhận slot và danh sách lịch được refetch sau khi huỷ | `523846e` |

## Kiểm tra đã chạy

| Lệnh | Kết quả |
| --- | --- |
| `npm run test -- --run` | Đạt — 4 file, 24 tests |
| `npm run lint` | Đạt |
| `npm run format:check` | Đạt |
| `npm run build` | Đạt — TypeScript và Vite production build |
| `docker compose -f deploy/compose.yaml up -d --build --wait` | Đạt — PostgreSQL, migrate, API và Nginx đều healthy |
| `npx playwright test` | Đạt — 8 E2E tests trên stack Compose/PostgreSQL |

## Ghi chú

- Test đổi ngày dùng ngày +7 và +8 để không tranh slot với các E2E đặt lịch dùng ngày +3 đến +6.
- E2E huỷ lịch kiểm tra thêm việc slot trở lại danh sách trống, không chỉ trạng thái dòng lịch.
- Các đầu việc C121, C122, C126, C127, C129 còn lại của tuần 3 đã có trong mã nguồn và được
  E2E/CI hiện tại bao phủ; lần kiểm chứng này chỉ bổ sung nửa đầu theo kế hoạch.
