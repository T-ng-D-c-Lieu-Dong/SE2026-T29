# Production Readiness Lab — Dịch vụ đặt lịch (Booking API & Platform)

Dự án triển khai dịch vụ đặt lịch để thực hành **CI/CD, container, release và rollback, khóa
triển khai, quan sát hệ thống và diễn tập sự cố**. Đã có UI, API, scripts và bằng chứng cục bộ;
triển khai trên máy demo, load test E15 và drill toàn trình vẫn cần hoàn thiện. Mô hình một VM
có thể gián đoạn khi recreate container; chưa có bằng chứng zero-downtime.

---

## 1. Kiến trúc hệ thống

Kiến trúc đích dùng Docker Compose trên một Linux VM theo
[ADR-001 đã Accepted](docs/architecture/adr/001-use-docker-compose.md). Local đã có
web/API/DB và observability overlay; production Compose hiện mới có API/DB. Sơ đồ dưới đây
mô tả đích triển khai, không phải kết quả xác nhận toàn bộ dịch vụ đã chạy trên máy demo:

```mermaid
flowchart TB
    User["Người dùng / Trình duyệt"]

    subgraph Host["Máy chủ Production — Docker Compose"]
        Web["Web — Nginx + React UI<br/>(Serve Frontend, Proxy /api)"]
        API["Booking API — FastAPI<br/>(Slots, Appointments, Health, Version)<br/>Tích hợp OpenTelemetry SDK & Fault Injection"]
        DB[("PostgreSQL 16<br/>Dữ liệu đặt lịch & Volume riêng")]

        subgraph Obs["Observability Stack"]
            Collector["OTel Collector<br/>Nhận traces, metrics, logs qua OTLP"]
            Prom["Prometheus<br/>Lưu trữ metrics & đánh giá alert rules"]
            Tempo["Tempo<br/>Lưu trữ distributed traces"]
            Loki["Loki<br/>Lưu trữ structured logs"]
            Blackbox["Blackbox Exporter<br/>Thăm dò trạng thái /health/ready"]
            Grafana["Grafana<br/>Dashboard tương quan Traces ↔ Logs ↔ Metrics"]
            AM["Alertmanager<br/>Discord cần webhook thật"]
        end

        Runner["Deploy & Rollback Runner<br/>(Scripts có khóa chống chạy đồng thời)"]
    end

    subgraph CICD["GitHub Actions"]
        CI["CI Workflow<br/>Lint, Format, Test, Smoke Test, Build"]
        Release["Release Workflow<br/>Gắn Git tag, build image & tạo manifest"]
        Rollback["Rollback Workflow<br/>Cần kết nối máy demo và state bền vững"]
    end

    User -->|HTTP| Web
    Web -->|Proxy /api| API
    API --> DB
    API -->|OTLP gRPC| Collector
    Collector --> Prom
    Collector --> Tempo
    Collector --> Loki
    Blackbox --> API
    Prom --> AM
    AM --> Discord["Discord Webhook"]
```

---

## 2. Cấu trúc thư mục

```text
SE2026-T29/
├── backend/                       # Mã nguồn backend (FastAPI, SQLAlchemy, Alembic)
│   ├── app/                       # Ứng dụng chính: API routers, Models, Services, Telemetry
│   ├── alembic/                   # Database migrations; review tương thích rollback
│   └── tests/                     # Unit tests & Integration tests
├── deploy/                        # Cấu hình triển khai Docker Compose
│   ├── compose.yaml               # Cấu hình cơ sở cho development
│   ├── compose.production.yaml    # Cấu hình production (immutable image digest)
│   ├── compose.observability.yaml # Cấu hình stack quan sát (Prometheus, Loki, Tempo, Grafana...)
│   └── observability/             # Cấu hình chi tiết Alertmanager, Prometheus rules, Dashboards
├── scripts/                       # Bộ công cụ tự động hóa triển khai & vận hành
│   ├── deploy.py / rollback.py    # Triển khai và rollback dựa trên release manifest
│   ├── deploy_lock.py             # Cơ chế khóa file chống deploy đồng thời
│   ├── release_manifest.py        # Schema và công cụ sinh/xác thực release manifest
│   ├── smoke_test.py              # Kiểm tra sức khỏe nghiệp vụ sau khi deploy
│   └── prepare_observability_drill.ps1 # Kịch bản tự động chuẩn bị diễn tập sự cố
└── docs/                          # Tài liệu kiến trúc, quy trình và nhật ký mốc
    ├── architecture/              # Tài liệu kiến trúc (Context, Module view, Runtime view, ADR)
    ├── releases/                  # Quy trình release, deploy và chính sách migration
    ├── tasks/                     # Kế hoạch công việc chi tiết (TASK-001 đến TASK-007)
    └── evidence/                  # Bằng chứng kiểm chứng theo mốc M0–M6
```

---

## 3. Trạng thái thực tế các Task

| ID | Task | Mốc | Trạng thái | Người phụ trách | Sản phẩm chính |
| --- | --- | --- | --- | --- | --- |
| **TASK-001** | [Xác nhận kiến trúc](docs/tasks/TASK-001-confirm-architecture.md) | M0 | **Done** | Phạm Minh Cương (23001840) | Context, Module view, Runtime view, ADR-001 Accepted và review migration |
| **TASK-002** | [Xây dựng Booking API](docs/tasks/TASK-002-booking-api.md) | M1 | **Done** | Phạm Minh Cương | FastAPI backend, PostgreSQL, transaction phòng chống double booking |
| **TASK-003** | [Xây dựng React UI](docs/tasks/TASK-003-react-ui.md) | M2 | **Done** | Lê Văn Cường | Giao diện đặt lịch, xem slot và quản lý lịch hẹn |
| **TASK-004** | [Container hóa và CI](docs/tasks/TASK-004-container-ci.md) | M3 | **In Progress** | Nguyễn Mai Hoàng Anh | Dockerfile tối ưu multi-stage, CI workflow kiểm tra lint & test |
| **TASK-005** | [Release, deploy và rollback](docs/tasks/TASK-005-release-deploy.md) | M4 | **Done** | Nguyễn Việt Anh | Release manifest, deploy/rollback automation, deploy lock, smoke test |
| **TASK-006** | [Observability và cảnh báo](docs/tasks/TASK-006-observability.md) | M5 | **In Progress** | Vũ Thành Công | OpenTelemetry runtime, Grafana dashboards, Alert rules, Fault injection |
| **TASK-007** | [Reliability demo và evidence](docs/tasks/TASK-007-reliability-demo.md) | M6 | **In Progress** | Nguyễn Việt Anh | Kịch bản diễn tập sự cố, bằng chứng cảnh báo và khôi phục hệ thống |

TASK-001 do **Phạm Minh Cương (23001840)** phụ trách. Xem
[review kiến trúc ngày 25/10](docs/evidence/2026-10-25-architecture-review.md) và
[bảng Tasks](docs/tasks/README.md) để theo dõi trạng thái thống nhất.

Đối chiếu tuần 2 ngày 28/10/2026: **48/50 đầu việc Done (96%)**; C058 và C060 vẫn
`In Progress` vì còn thiếu required reviewer và lần deploy thật trên demo host. Xem
[báo cáo đối chiếu tuần 2](docs/evidence/2026-10-28-week2-reconciliation.md).

---

## 4. Hướng dẫn phát triển cục bộ

### 4.1. Thiết lập môi trường Backend

Yêu cầu: Python 3.12+ và PostgreSQL 16 (hoặc Docker).

```bash
# Di chuyển vào thư mục backend
cd backend

# Khởi tạo và kích hoạt virtual environment
python -m venv .venv
# Trên Windows:
.venv\Scripts\activate
# Trên Linux/macOS:
source .venv/bin/activate

# Cài đặt backend kèm các gói dev
python -m pip install -e ".[dev]"
```

### 4.2. Chạy Linter & Code Formatter

Dự án sử dụng [Ruff](https://astral.sh/ruff) để duy trì chất lượng mã nguồn:

```bash
# Kiểm tra lỗi linter
python -m ruff check backend

# Tự động sửa lỗi có thể tự sửa
python -m ruff check --fix backend

# Kiểm tra định dạng code
python -m ruff format --check backend
```

### 4.3. Chạy Kiểm thử (Tests)

Unit tests backend có thể chạy cục bộ độc lập; số lượng và kết quả ghi theo từng lần kiểm chứng:

```bash
pytest backend/tests/unit
```

Đối với các integration tests yêu cầu database:

```bash
# Khởi động PostgreSQL container dành riêng cho test
docker compose -f backend/compose.test.yaml up -d

# Thiết lập biến môi trường và chạy test
# Trên PowerShell:
$env:TEST_DATABASE_URL="postgresql+asyncpg://booking:booking@localhost:55432/booking_test"
pytest

# Trên Linux/macOS:
export TEST_DATABASE_URL="postgresql+asyncpg://booking:booking@localhost:55432/booking_test"
pytest
```

### 4.4. Khởi chạy Observability Stack

Khởi chạy đồng thời Booking API cùng toàn bộ hệ thống thu thập logs, metrics, traces:

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.observability.yaml up -d
```

Các cổng dịch vụ mặc định:
- **Booking API**: `http://localhost:8000` (OpenAPI: `http://localhost:8000/docs`)
- **Grafana**: `http://localhost:3000` (User/Password: `admin` / `admin`)
- **Prometheus**: `http://localhost:9090`
- **Alertmanager**: `http://localhost:9093`

---

## 5. Tài liệu tham chiếu chi tiết

1. [Tài liệu kiến trúc tổng thể](docs/architecture/README.md)
2. [Quy trình phát hành và triển khai (Release & Deploy Process)](docs/releases/release-process.md)
3. [Chính sách tương thích Migration](docs/releases/migration-policy.md)
4. [Hướng dẫn vận hành Observability cục bộ](docs/devops/observability-local.md)
5. [Runbook xử lý cảnh báo](docs/runbooks/observability-alerts.md)
6. [Bảng kiểm chứng Evidence (M0–M6)](docs/evidence.md)
