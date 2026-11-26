# TASK-006 — Kiểm chứng local ngày 26/11/2026

Owner theo bảng phân công: Vũ Thành Công. Source commit: `5e71134`.
Môi trường: Windows, Docker Desktop Linux Engine 29.9.2, Compose local + observability
+ override Docker Desktop. Backend báo release `dev`, commit `local`; đây không phải image
release trên demo host. Phép đo được thực hiện khoảng 14:00–14:05 UTC.

## Kết quả thực hiện

- Đã khởi động Docker Desktop, build frontend/backend và chạy toàn bộ stack bằng
  `docker compose --env-file deploy/observability.env -f deploy/compose.yaml
  -f deploy/compose.observability.yaml -f deploy/compose.observability.docker-desktop.yaml
  up -d --build --wait --wait-timeout 240`: exit 0; tất cả dịch vụ chạy, migration exit 0.
- Smoke sau build: readiness, version, xem slot → đặt → hủy đều pass; xem `smoke.txt`.
- 17 tests telemetry, request logging và observability alert traffic pass.
- `promtool check rules`: SUCCESS, 6 recording/alert rules.
- `amtool check-config`: SUCCESS, 1 receiver.
- `otelcol-contrib validate`: exit 0.
- Cả 6 scrape target đều UP tại thời điểm snapshot: xem `targets.json`.
- Snapshot recording/alert rules thực tế: `rules.json`. Snapshot không chứng minh alert firing.
- Tempo trả trace `8c47c03547e8552cad989795564c3065`, request `GET /health/ready`.
  Loki trả đúng một log cùng trace ID, status 200, route `/health/ready`, release/service_version
  `dev`: xem `tempo-search.json`, `correlated-logs.json`.

## Giới hạn và công việc còn lại

- E09: đã xác nhận truy vấn trace → log local cho request thành công. Chưa có request lỗi,
  ảnh dashboard/exemplar và xác nhận điều hướng UI; chưa chốt E09 end-to-end.
- E10: lệnh dừng Collector để thử outage bị automatic approval review từ chối với
  `blocked by policy`, không cung cấp lý do chi tiết. Không thực hiện outage runtime.
  Unit tests đạt không thay thế thử booking với Collector thực sự ngừng chạy.
- E11/E16: chưa thực hiện fault/probe outage, đo pending/firing/resolved và delivery Discord.
- Loki `/ready` ban đầu trả 503; sau khi Compose hoàn tất Loki healthy. Query log đã thành công.
- Truy vấn Tempo từ backend ban đầu lỗi DNS vì backend chỉ ở application network;
  truy vấn từ Grafana trên observability network thành công. Không cần mở thêm port.
- Các snapshot có thể chứa dữ liệu từ trước lần build: không suy diễn tất cả telemetry
  trong snapshot đều do image vừa build sinh ra.
- CPU/container metrics trên máy này phản ánh Linux VM Docker Desktop. Cần chạy lại trên
  demo Linux cùng release/digest thật, webhook thật và lưu timeline/ảnh trước khi chốt task.

TASK-006 vẫn **In Progress**. Stack local được giữ chạy để tiếp tục xem Grafana tại
`http://localhost:3000` và Prometheus tại `http://localhost:9090`.

## Bổ sung sau khi pull main

- Nhánh `docs/task-006-observability-evidence` được fast-forward tới main `6944a36`.
- Chạy công cụ mới `python -m scripts.capture_observability --output
  docs/evidence/observability/2026-11-26-local/prometheus-snapshot` lúc
  `2026-11-26T14:12:55.963114+00:00`: targets, rules, probe, HTTP metrics checks đều đạt.
- Snapshot tại `prometheus-snapshot/`; đây là dữ liệu stack đang chạy từ lần build trước khi
  pull, không phải bằng chứng backend `6944a36` đã được rebuild/deploy.
- 3 regression tests của công cụ kiểm tra dữ liệu rỗng, lỗi kết nối và metric có customer label.

## Kiểm chứng rule E11 hiện tại

- Bổ sung ba scenario promtool: 4% lỗi dưới ngưỡng với đủ tải; burst ngắn không giữ đủ
  hai phút; alert đã firing rồi resolved sau khi counter lỗi ngừng tăng.
- Chạy toàn bộ sáu scenario bằng `prom/prometheus:v3.13.5` và rule source hiện tại:
  SUCCESS, xem `promtool-tests.txt`. Đây là dữ liệu tổng hợp, không phải incident runtime.
- Thử ban đầu tại đúng biên 5% cho thấy phép tính rate/division dấu phẩy động có thể tạo
  giá trị lớn hơn 0.05 rất nhỏ và kích hoạt rule. Không sửa threshold vận hành; bài kiểm
  tra dưới ngưỡng sử dụng 4%, không tuyên bố kiểm chứng chính xác tại biên 5%.
- Công cụ snapshot kiểm tra thêm rule health và hold duration 120/60/300 giây;
  6 tests đạt, bao gồm từ chối rule HighErrorRate 30 giây và evaluation lỗi.
- Snapshot `prometheus-rule-validation/` xác nhận cả bốn checks đạt với rule runtime hiện tại.
  Việc này không xác nhận thông báo Discord hoặc thay thế drill thực tế.
