# Chạy observability stack

Tài liệu này dùng cho TASK-006 trên máy Linux có Docker Engine 24+ và Docker Compose v2. Stack
gồm OTel Collector, Prometheus, Tempo, Loki, Grafana, Alertmanager, blackbox exporter,
node-exporter và cAdvisor. Dữ liệu telemetry được giữ bảy ngày trong các named volume.

## Chuẩn bị cấu hình

Từ thư mục gốc repository:

```bash
cp deploy/observability.env.example deploy/observability.env
cp deploy/observability/alertmanager/discord-webhook-url.example \
  deploy/observability/alertmanager/discord-webhook-url
```

Sửa `deploy/observability.env`, đặt mật khẩu Grafana khác mặc định. Ghi duy nhất URL webhook
Discord thật vào `deploy/observability/alertmanager/discord-webhook-url`. Hai file local này không
được commit; file webhook đã nằm trong `.gitignore`.

Trên Windows PowerShell, có thể tạo hai file local và sinh mật khẩu Grafana ngẫu nhiên bằng:

```powershell
.\scripts\prepare_observability_drill.ps1
```

Khi đã có webhook thật, chạy lại mà không ghi URL vào lịch sử lệnh bằng cách đọc từ clipboard:

```powershell
.\scripts\prepare_observability_drill.ps1 -DiscordWebhookUrl (Get-Clipboard)
```

Script không in mật khẩu hoặc webhook ra terminal. Nếu chưa truyền webhook, file nhận giá trị
placeholder và phải được cập nhật trước khi chạy alert drill.

Khi chạy bằng Docker Desktop trên Windows, thêm override tương thích để bỏ mount propagation
`rslave` mà Docker Desktop không hỗ trợ:

```powershell
docker compose `
  --env-file deploy/observability.env `
  -f deploy/compose.yaml `
  -f deploy/compose.observability.yaml `
  -f deploy/compose.observability.docker-desktop.yaml `
  up -d --build --wait --wait-timeout 240
```

Trong chế độ này, node-exporter và cAdvisor phản ánh Linux VM của Docker Desktop, không phản ánh
toàn bộ máy Windows. Evidence cuối cho tài nguyên host vẫn phải lấy trên máy demo Linux.

`OBS_BIND_ADDRESS=127.0.0.1` chỉ cho phép truy cập dashboard từ máy chạy stack. Trên máy demo,
chỉ đổi thành `0.0.0.0` khi các port được giới hạn bằng firewall, LAN riêng hoặc VPN.

## Khởi động

Chạy ứng dụng local và observability bằng hai Compose files:

```bash
docker compose \
  --env-file deploy/observability.env \
  -f deploy/compose.yaml \
  -f deploy/compose.observability.yaml \
  up -d --build --wait --wait-timeout 240
```

Overlay tự bật `BOOKING_TELEMETRY_ENABLED=true` và gửi OTLP/gRPC tới Collector. Các địa chỉ mặc
định trên host:

| Thành phần | URL | Mục đích |
| --- | --- | --- |
| Booking API | `http://localhost:8000` | Tạo request và kiểm tra health |
| Grafana | `http://localhost:3000` | Dashboard, trace và log correlation |
| Prometheus | `http://localhost:9090` | Targets, rules và PromQL |
| Alertmanager | `http://localhost:9093` | Trạng thái alert và receiver |

Tempo, Loki, Collector, exporters và database chỉ nằm trong Docker networks; không mở port ra
host.

Trên máy demo dùng image backend từ release manifest, thay file ứng dụng local bằng
`deploy/compose.production.yaml` trong cùng câu lệnh.

## Kiểm tra sau khi khởi động

```bash
curl --fail http://localhost:8000/health/ready
curl --fail http://localhost:9090/-/ready
curl --fail http://localhost:9093/-/ready
curl --fail http://localhost:3000/api/health
```

Mở `http://localhost:9090/targets` và xác nhận các job sau đều `UP`:

- `otel-collector`
- `booking-api-readiness`
- `blackbox-exporter`
- `node-exporter`
- `cadvisor`

Sau khi gọi API vài lần, chạy các truy vấn nhanh trong Prometheus:

```promql
sum(rate(http_server_duration_milliseconds_count{service_name="booking-api"}[1m]))
```

```promql
probe_success{job="booking-api-readiness"}
```

Trong Grafana, mở thư mục **Production Readiness** và dashboard **Booking API — Production
Readiness**. Version, request rate, probe và tài nguyên máy/container phải có dữ liệu. Quy trình
kiểm tra metric → trace → log và tên ảnh cần lưu nằm trong
[`docs/evidence/observability/README.md`](../evidence/observability/README.md).

## Kiểm tra Collector outage — E10

```bash
docker compose \
  --env-file deploy/observability.env \
  -f deploy/compose.yaml \
  -f deploy/compose.observability.yaml \
  stop otel-collector

python -m scripts.smoke_test --base-url http://localhost:8000

docker compose \
  --env-file deploy/observability.env \
  -f deploy/compose.yaml \
  -f deploy/compose.observability.yaml \
  start otel-collector
```

Smoke test phải hoàn thành trong khi Collector dừng. Ghi thời gian và kết quả thật vào evidence;
telemetry phát sinh trong khoảng outage có thể bị mất khi queue đầy.

## Kiểm tra HighErrorRate — E11

Đây là traffic dành riêng cho alert drill, không thay thế kịch bản k6 và báo cáo tải E15 của
TASK-007. Bật fault có thời hạn dài hơn bài chạy, recreate riêng backend, rồi chạy trình tạo lỗi:

```powershell
$env:BOOKING_FAULT_MODE = "error"
$env:BOOKING_FAULT_RATE = "1.0"
$env:BOOKING_FAULT_UNTIL = (Get-Date).ToUniversalTime().AddMinutes(5).ToString("o")

docker compose `
  --env-file deploy/observability.env `
  -f deploy/compose.yaml `
  -f deploy/compose.observability.yaml `
  -f deploy/compose.observability.docker-desktop.yaml `
  up -d --no-deps --force-recreate --wait backend

python -m scripts.observability_alert_traffic --rate 2 --duration 210
```

Theo dõi `HighErrorRate` qua Prometheus và Alertmanager, ghi timestamp `pending`, `firing`, thông
báo Discord và `resolved`. Sau bài chạy, luôn tắt fault và recreate backend:

```powershell
$env:BOOKING_FAULT_MODE = "off"
Remove-Item Env:BOOKING_FAULT_RATE -ErrorAction SilentlyContinue
Remove-Item Env:BOOKING_FAULT_UNTIL -ErrorAction SilentlyContinue

docker compose `
  --env-file deploy/observability.env `
  -f deploy/compose.yaml `
  -f deploy/compose.observability.yaml `
  -f deploy/compose.observability.docker-desktop.yaml `
  up -d --no-deps --force-recreate --wait backend
```

Trình tạo traffic chỉ đạt khi toàn bộ response có status mong đợi và không có lỗi kết nối. Nó
in đúng một JSON summary để lưu evidence, không in request body hoặc dữ liệu khách hàng.

## Dừng stack

```bash
docker compose \
  --env-file deploy/observability.env \
  -f deploy/compose.yaml \
  -f deploy/compose.observability.yaml \
  down
```

Lệnh trên giữ cả booking và telemetry volumes. Không thêm `-v` trên máy demo vì tùy chọn đó xóa
PostgreSQL, Prometheus, Tempo, Loki, Grafana và Alertmanager data.

## Xử lý sự cố

| Triệu chứng | Kiểm tra |
| --- | --- |
| Dashboard không có HTTP metrics | Backend có `BOOKING_TELEMETRY_ENABLED=true`; target `otel-collector` đang `UP` |
| Có metric nhưng không có trace | Log Collector và Tempo; kiểm tra pipeline `traces` |
| Có trace nhưng link log rỗng | Loki có structured metadata `trace_id`; datasource UIDs là `tempo` và `loki` |
| `ApiProbeDown` luôn firing | Target blackbox dùng `http://backend:8000/health/ready`; backend và DB healthy |
| Discord không nhận alert | File webhook chứa đúng một URL, Alertmanager đã reload và receiver tên `discord` |
| cAdvisor không chạy | Máy demo phải là Linux và cho phép các bind mount `/sys`, `/var/lib/docker`, `/dev/disk` |
