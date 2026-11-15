# Observability stack trên máy demo — tài nguyên và kiểm chứng (TASK-006)

- **Ngày thực hiện**: 15/11/2026
- **Người phụ trách**: Nguyễn Mai Hoàng Anh (23001824)
- **Máy**: VM Multipass `booking-demo`, Ubuntu 24.04.5, 2 vCPU, 3,9 GB RAM, không swap, disk 24 GB
- **Release đang chạy**: `v0.2.1` (commit `8e9af63`), deploy qua pipeline ngày 28/10
- **Cấu hình**: nhánh `feat/task-006-obs-demo-host`, commit `82427df`
- **Dữ liệu gốc**: [k6-summary.json](2026-11-15-demo-host/k6-summary.json),
  [memory-under-load.log](2026-11-15-demo-host/memory-under-load.log)

**Phạm vi:** stack observability được dựng bằng `docker compose` trực tiếp trên máy demo, dùng đúng
`.env.production` do lần deploy `v0.2.1` sinh ra. Chưa phải một lần deploy qua `deploy.yml` có
overlay: việc đó cần một release mới chứa `--compose-overlay`. Webhook Discord vẫn là placeholder,
nên chưa kiểm chứng thông báo Discord.

## 1. Stack và trạng thái

12 container trong project `booking`: `web`, `backend`, `db` cùng `otel-collector`, `prometheus`,
`tempo`, `loki`, `grafana`, `alertmanager`, `blackbox-exporter`, `node-exporter`, `cadvisor`.

| Kiểm tra | Kết quả |
| --- | --- |
| Prometheus targets | 6/6 `up`: prometheus, otel-collector, booking-api-readiness, blackbox-exporter, node-exporter, cadvisor |
| Probe qua web | `probe_success{instance="http://web/health/ready"} = 1` |
| Metric HTTP từ API | 165 series `http_server*`, nhãn `service_version="v0.2.1"` |
| Trace | Tempo có trace `booking-api` (`GET /api/slots`, `GET /api/version`) |
| Log | Loki có label `service_name`, `deployment_environment` |
| Grafana 13.2.4 | `/api/health` ok; datasource Prometheus, Tempo, Loki; dashboard "Booking API — Production Readiness" |
| Cổng quản trị | Gọi `10.97.0.43:3000`, `:9090`, `:9093` từ laptop đều không kết nối được (bind `127.0.0.1`) |

## 2. Tài nguyên

### Khi rảnh (sau khi stack chạy 60 giây)

| Container | RAM |
| --- | --- |
| grafana | 260,8 MiB |
| cadvisor | 142,0 MiB |
| prometheus | 136,1 MiB |
| backend | 108,4 MiB |
| tempo | 94,8 MiB |
| loki | 82,9 MiB |
| db | 50,2 MiB |
| otel-collector | 49,2 MiB |
| alertmanager | 37,4 MiB |
| blackbox-exporter | 26,6 MiB |
| web | 10,1 MiB |
| node-exporter | 8,7 MiB |
| **Tổng container** | **khoảng 1,0 GB** |

Máy: used 1.282 MB, available 2.626 MB. Disk dùng 7,8 GB / 24 GB, trong đó image 4,4 GB và volume
553 MB (phần lớn là `grafana_data` 485 MB).

### Khi có tải 10 req/s trong 3 phút

k6 `grafana/k6:2.3.0` chạy ngay trên VM với `loadtest/booking.js`, `BASE_URL=http://localhost`
(qua Nginx), `DURATION=3m`. RAM lấy mẫu mỗi 20 giây:

| Chỉ số | Giá trị |
| --- | --- |
| RAM used cao nhất | 1.397 MB |
| RAM available thấp nhất | 2.512 MB |
| Load average cao nhất (2 vCPU) | 0,87 |
| Request | 1.804, tốc độ 10,02 req/s |
| Lỗi HTTP | 0 |
| Checks | 4.690 / 4.690 pass |
| Độ trễ | p50 17,1 ms; p90 27,2 ms; p95 30,7 ms; max 138,8 ms |

**Kết luận:** VM 4 GB đủ cho app và cả stack observability ở tải 10 req/s, còn dư khoảng 2,5 GB.
Không cần nâng RAM cho diễn tập. VM không có swap, nên nếu sau này thêm tải lớn hơn thì theo dõi
`node_memory_MemAvailable_bytes`.

Số liệu trên là lần chạy 3 phút để đo tài nguyên, không thay thế E15 (10 phút).

## 3. Lỗi `--remove-orphans` và cách sửa

Overlay phải chung Compose project với app vì nó đổi env telemetry của `backend`. Lệnh compose sinh
từ `scripts.deploy.build_compose_up_command` trên máy demo:

| Lệnh | Container observability còn lại |
| --- | --- |
| `-f compose.production.yaml up -d --remove-orphans` (như trước khi sửa) | **0** — cả 9 bị xoá |
| `-f compose.production.yaml -f compose.observability.yaml up -d --remove-orphans` | 9 |
| Chạy lại lệnh có overlay | 9, ID container không đổi |

Sau lần cuối, smoke test qua web pass đủ `readiness_check`, `version_check`, `business_flow`.
Bản sửa: tham số `--compose-overlay` trong `deploy.py`/`rollback.py`, và workflow tự truyền overlay
khi state dir có `observability.env`.

## 4. Còn thiếu

- Deploy một release mới qua `deploy.yml` để overlay được dựng bằng pipeline.
- Webhook Discord thật cho Alertmanager (E11).
- E09, E11, E16 trên máy demo thuộc TASK-006/TASK-007; tài liệu này chỉ chứng minh hạ tầng sẵn sàng.
