# Frontend — Đặt lịch hẹn

React + Vite + TypeScript cho dịch vụ đặt lịch. UI gọi API thật qua đường dẫn tương đối `/api`,
hiển thị thời gian theo `Asia/Ho_Chi_Minh`, và là công cụ tạo request thật khi demo.

## Yêu cầu

- Node.js 22.12 trở lên (khuyến nghị 22 LTS hoặc 24)
- Booking API đang chạy ở `http://localhost:8000` (xem `backend/README.md`)
- Docker (chỉ cần cho phần container và E2E trên stack Compose)

## Cài đặt

```bash
cd frontend
npm ci
```

## Chạy ở môi trường phát triển

```bash
npm run dev
```

Vite chạy ở `http://localhost:5173` và proxy `/api` sang backend. Nếu backend ở địa chỉ khác:

```bash
$env:VITE_PROXY_TARGET = "http://localhost:8000"   # PowerShell
npm run dev
```

## Biến môi trường

| Biến                | Nơi dùng        | Mặc định                | Ý nghĩa                                            |
| ------------------- | --------------- | ----------------------- | -------------------------------------------------- |
| `VITE_PROXY_TARGET` | Vite dev server | `http://localhost:8000` | Backend nhận request `/api` khi chạy `npm run dev` |
| `E2E_BASE_URL`      | Playwright      | `http://localhost:8080` | URL của UI đã build (Nginx/Compose) khi chạy E2E   |

Không commit file `.env.local` hay bất kỳ secret nào.

## Script

| Lệnh                    | Việc                                             |
| ----------------------- | ------------------------------------------------ |
| `npm run dev`           | Dev server có proxy `/api`                       |
| `npm run build`         | Type-check (`tsc --noEmit`) rồi build ra `dist/` |
| `npm run preview`       | Xem thử bản build ở `http://localhost:4173`      |
| `npm run lint`          | ESLint cho toàn bộ `src/`, `e2e/`, config        |
| `npm run format:check`  | Kiểm tra Prettier                                |
| `npm test`              | Vitest watch mode                                |
| `npm run test -- --run` | Chạy toàn bộ unit/component test một lần         |
| `npm run test:e2e`      | Playwright E2E (cần stack đang chạy)             |

## Kiểm thử

### Unit và component test

```bash
npm run test -- --run
```

Bao phủ: API client (409, traceparent, retry có giới hạn cho GET, timeout), helper thời gian
theo `Asia/Ho_Chi_Minh`, slot list (loading/rỗng/lỗi), đặt lịch thành công, xung đột 409, huỷ lịch
có xác nhận và trường hợp bỏ xác nhận.

### E2E (Playwright)

E2E chạy trên UI đã build phục vụ bởi Nginx trong stack Compose:

```bash
# từ thư mục gốc repository
docker compose -f deploy/compose.yaml up -d --build --wait

cd frontend
npx playwright install --with-deps chromium   # lần đầu
npm run test:e2e
```

Chạy bộ smoke sau khi deploy (tag `@smoke`):

```bash
npx playwright test --grep @smoke
```

Trỏ tới môi trường khác (ví dụ máy demo):

```bash
$env:E2E_BASE_URL = "http://demo-host:8080"
npm run test:e2e
```

Report HTML nằm ở `frontend/playwright-report/` (artifact CI `playwright-report`).

## Docker và Nginx

```bash
docker build -t booking-frontend:local frontend
docker run --rm -p 8080:80 --network booking_local_net booking-frontend:local
```

- Multi-stage: `node:22.20.0-alpine` build → `nginx:1.27-alpine` serve.
- Nginx phục vụ SPA (`try_files ... /index.html`), proxy `/api/` tới `backend:8000`.
- Log access dạng JSON để Loki đọc được; `gzip` bật; asset có hash được cache 1 năm,
  `index.html` dùng `no-cache`.
- Healthcheck nội bộ: `GET /healthz`.

## Cấu trúc

```text
frontend/
├── e2e/                     # Playwright specs + helper
├── src/
│   ├── api/                 # HTTP client (typed errors, retry), endpoint functions
│   ├── components/          # Slot list, form, danh sách, dialog, footer
│   ├── pages/BookingPage.tsx
│   ├── test/setup.ts
│   ├── time.ts              # Định dạng giờ theo Asia/Ho_Chi_Minh
│   └── types.ts             # Kiểu dữ liệu khớp schema backend
├── Dockerfile
├── nginx.conf
├── playwright.config.ts
└── vite.config.ts
```

## Trạng thái E06

UI phản ánh response thật của API: loading/empty/error/success, lỗi `409` hiển thị
"Slot đã có người đặt" và không báo thành công, footer đọc `/api/version`. Kết quả kiểm chứng
được ghi trong `docs/evidence.md` (E06) và `docs/evidence/frontend/`.
