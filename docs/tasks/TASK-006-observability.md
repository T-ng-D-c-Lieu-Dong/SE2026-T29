# TASK-006 — Observability và cảnh báo

- Trạng thái: **In Progress**
- Người phụ trách: **Vũ Thành Công**
- Phối hợp backend: **Phạm Minh Cương (23001840)**
- Mốc: **M5 — Observability**
- Phụ thuộc: TASK-004

## Mục tiêu

Thu thập metrics, traces và logs để phát hiện, điều tra lỗi và liên hệ lỗi với release.

## Công việc

- Instrument FastAPI bằng OpenTelemetry và export qua Collector.
- Cấu hình Prometheus, Tempo, Loki, Grafana và Alertmanager.
- Thêm correlation bằng trace ID, service version và release.
- Tạo dashboard cho request rate, error rate, latency và booking conflicts.
- Tạo alert cho tỷ lệ 5xx và blackbox readiness probe.
- Kiểm tra booking vẫn hoạt động khi Collector không sẵn sàng.

## Tiêu chí hoàn thành

- Từ một request lỗi có thể đi từ dashboard tới trace và log liên quan.
- Metric labels không chứa UUID, trace ID hoặc dữ liệu khách hàng.
- Probe phát hiện API ngừng đáp ứng ngay cả khi HTTP counter không tăng.
- Kiểm chứng E09–E11 và E16 trong [Evidence](../evidence.md) đạt.

## Tiến độ hiện tại

- Đã có instrumentation FastAPI/SQLAlchemy, span nghiệp vụ, metric booking conflict, JSON
  request log có trace correlation và OTLP exporter với queue/timeout hữu hạn.
- Đã có fault injection `error`/`latency` có tỷ lệ và thời điểm tự tắt, thực thi trước khi ghi DB.
- Đã có dashboard Grafana cho golden signals, booking conflict, probe, tài nguyên host/container,
  version và mốc deploy; các biểu thức PromQL đã được kiểm tra bằng `promtool`.
- Đã có provisioning cho liên kết Prometheus exemplar ↔ Tempo trace ↔ Loki log, alert rules
  `HighErrorRate`, `ApiProbeDown`, `HighLatencyP95`, runbook và bộ truy vấn thu thập evidence.
- Đã có Compose overlay và cấu hình Collector, Prometheus, Tempo, Loki, Grafana, Alertmanager,
  blackbox exporter, node-exporter, cAdvisor; CI kiểm tra cấu hình bằng validator của từng công cụ.
- Còn thiếu lần chạy trên máy demo, webhook thật và evidence từ reliability drill; vì vậy task
  chưa thể chuyển sang `Done`.

## Đối chiếu tuần 2 ngày 28/10/2026

- C061–C070 và C091–C100 đã có code, test hoặc local evidence tương ứng.
- Bổ sung explicit HTTP duration buckets và trace-based exemplar filter tại `072ba36`.
- Trạng thái task vẫn là `In Progress` vì tiêu chí hoàn thành yêu cầu demo chung, webhook thật và
  reliability drill; xem [bảng đối chiếu](../evidence/2026-10-28-week2-reconciliation.md).

## Cập nhật ngày 26/11/2026

- Code main đã có [hạ tầng observability trên demo host ngày 15/11](../evidence/observability/2026-11-15-demo-host-observability.md).
  Báo cáo này xác nhận targets, metrics, traces, logs và tài nguyên; webhook ở lần chạy đó vẫn
  là placeholder. Không còn coi việc dựng stack demo là toàn bộ phần thiếu.
- Đã thêm `python -m scripts.capture_observability` để lưu snapshot Prometheus và kiểm tra
  targets, alert rules, probe cùng một số nhãn metric bị cấm; không suy diễn snapshot thành drill pass.
- [Kiểm chứng local 26/11](../evidence/observability/2026-11-26-local/README.md):
  build stack, smoke booking và truy vấn trace → log đạt; snapshot mới có cả bốn checks đạt.
- Báo cáo rehearsal E11 ngày 06/11 ghi `for: 30s`, trong khi rule hiện tại là `for: 2m`.
  Kết quả lịch sử cần được đối chiếu đúng config/release và artifact gốc trước khi dùng để
  nghiệm thu rule hiện tại. Báo cáo demo 15/11 cũng ghi webhook chưa cấu hình ở lần chạy đó.
- Giữ `In Progress`: cần thống nhất evidence E11 theo đúng môi trường/config, xác nhận
  điều hướng dashboard → trace lỗi → log và bổ sung E09/E16 trên demo host.
- Đã bổ sung và chạy đạt sáu scenario promtool cho alert (bao gồm burst ngắn, dưới
  ngưỡng và phục hồi E11); sáu tests công cụ snapshot đạt. Runtime snapshot xác nhận
  rule health và `for` hiện tại là 120/60/300 giây. Chi tiết ở evidence local 26/11.
