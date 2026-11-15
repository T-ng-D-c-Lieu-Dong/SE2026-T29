# Máy demo và GitHub self-hosted runner

Tài liệu này dùng cho TASK-004 (giai đoạn B trong [DevOps README](README.md)). Kết quả cuối cùng là
một máy Linux chạy Docker, có thư mục state cố định và một GitHub self-hosted runner gắn label
`demo`. Workflow deploy và rollback chỉ chạy trên runner này.

## Cấu hình đề xuất

| Mục | Giá trị |
| --- | --- |
| Hệ điều hành | Ubuntu 24.04 LTS |
| Tài nguyên | 2 vCPU, 6 GB RAM, 30 GB disk (đủ cho app và observability stack) |
| Thư mục state | `/opt/booking/state` — chứa `current-manifest.json`, `previous-manifest.json`, `.env.production`, `history.json` |
| Runner label | `self-hosted`, `linux`, `demo` |

Không lưu state trong workspace của runner: workspace bị xoá hoặc checkout lại ở mỗi job, nên
manifest dùng để rollback sẽ mất.

## 1. Tạo VM bằng Multipass

Bỏ qua bước này nếu chạy trực tiếp trên một máy Linux.

```bash
multipass launch 24.04 --name booking-demo --cpus 2 --memory 6G --disk 30G
multipass shell booking-demo
```

Lấy IP của VM để mở UI từ máy host: `multipass info booking-demo`.

## 2. Cài Docker và tạo thư mục state

Trong VM, lấy repository rồi chạy script bootstrap bằng quyền root. Script cài Docker Engine,
Docker Compose v2, Python 3 và GitHub CLI; tạo `/opt/booking/state` thuộc user chạy runner và thêm
user đó vào nhóm `docker`. Script chạy lại nhiều lần không gây hại.

```bash
git clone https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29.git
cd SE2026-T29
sudo scripts/bootstrap-host.sh
```

Đăng xuất rồi đăng nhập lại để nhóm `docker` có hiệu lực, sau đó kiểm tra:

```bash
docker run --rm hello-world
docker compose version
ls -ld /opt/booking/state
```

## 3. Cài self-hosted runner

Cần quyền admin repository để lấy registration token. Người có quyền admin mở
**Settings → Actions → Runners → New self-hosted runner**, chọn Linux x64 và copy các lệnh tải
runner trên trang đó (trang luôn ghi đúng phiên bản và checksum mới nhất). Ở bước `config.sh`, thêm
label và tên cố định:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
# Chạy các lệnh curl/tar copy từ trang "New self-hosted runner"
./config.sh \
  --url https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29 \
  --token <REGISTRATION_TOKEN> \
  --name booking-demo \
  --labels demo \
  --unattended
sudo ./svc.sh install "$USER"
sudo ./svc.sh start
```

Runner chạy như một systemd service dưới user hiện tại, nên dùng được Docker mà không cần `sudo`.
Registration token hết hạn sau một giờ; không commit hoặc dán token vào issue.

## 4. Kiểm tra runner

- **Settings → Actions → Runners** hiện `booking-demo` trạng thái **Idle** với label `demo`.
- Trên VM: `sudo ./svc.sh status` báo `active (running)`.
- Log runner nằm ở `~/actions-runner/_diag/`.

## 5. GitHub Environment `demo`

`deploy.yml` chạy trong environment `demo`, nên mọi lần deploy (kể cả lần tự kích hoạt sau release)
dừng ở trạng thái **Waiting** cho tới khi reviewer duyệt. Người có quyền admin tạo environment một
lần trong **Settings → Environments → New environment**:

| Cài đặt | Giá trị |
| --- | --- |
| Name | `demo` |
| Required reviewers | Ít nhất một thành viên khác người push tag, ví dụ người phụ trách TASK-005 |
| Prevent self-review | Bật |
| Deployment branches and tags | **Selected branches and tags**, thêm rule kiểu tag `v*` và branch `main` |
| Environment variable (tuỳ chọn) | `BOOKING_STATE_DIR` nếu không dùng `/opt/booking/state` |

Rule `v*` cho phép job chạy từ tag release; rule `main` cần cho lần deploy tự động, vì workflow
`workflow_run` chạy trên nhánh mặc định.

`rollback.yml` cố ý không dùng environment này: rollback luôn do người bấm `workflow_dispatch`
trong lúc sự cố, và bước chờ duyệt sẽ ăn vào mục tiêu khôi phục trong 5 phút.

## 6. Deploy và rollback qua pipeline

| Thao tác | Cách chạy | Ghi chú |
| --- | --- | --- |
| Deploy tự động | Push tag `vX.Y.Z` → `release.yml` thành công → `deploy.yml` chờ duyệt | Chỉ kích hoạt khi `deploy.yml` đã nằm trên `main` |
| Deploy thủ công | **Actions → Deploy to Demo Host → Run workflow**, nhập tag | Tag phải có GitHub Release kèm `<tag>.json` |
| Rollback | **Actions → Rollback Deployment → Run workflow**, ghi lý do | Để trống `target_manifest` để về `previous-manifest.json` |

Hai workflow dùng chung concurrency group `deploy-demo`: một job đang chạy thì job sau xếp hàng.
GitHub chỉ giữ một job chờ trong mỗi group, nên nếu xếp liền hai lần, lần chờ cũ bị huỷ.

Mỗi lần chạy upload artifact `deploy-<tag>-<attempt>` hoặc `rollback-<run>-<attempt>` gồm log,
`current-manifest.json`, `previous-manifest.json`, `history.json` và `docker compose ps`.

## Lưu ý bảo mật

- Repository là public. Không workflow nào được chạy trên self-hosted runner với trigger
  `pull_request`, vì code từ fork sẽ chạy trên máy demo. CI thường vẫn dùng `ubuntu-latest`; chỉ
  `deploy.yml`, `rollback.yml` và workflow `loadtest.yml` thủ công dùng `runs-on: [self-hosted, demo]`.
- Giữ cài đặt **Settings → Actions → General → Fork pull request workflows** ở mức yêu cầu duyệt.
- Không mở port SSH của VM ra Internet; truy cập từ xa khi demo dùng Tailscale.

## 7. Phối hợp load test và release drill

Workflow **Load Test on Demo Host** chỉ nhận `workflow_dispatch` trên `main`, gọi web
`http://localhost` port 80 và upload artifact ngay cả khi thresholds thất bại.
Fault config được đưa vào release manifest cho tag `*-drill`, rồi deploy/rollback ghi
vào env tại state dir. Chi tiết deadline, smoke và evidence:
[Release drill](../releases/drill-release.md).

## 8. Observability stack trên máy demo

`deploy.yml` và `rollback.yml` dựng thêm `deploy/compose.observability.yaml` khi state dir có
`observability.env`; không có file này thì chỉ chạy app. Overlay nằm chung Compose project
`booking` với app, nên mọi lệnh deploy/rollback phải truyền `--compose-overlay`. Nếu thiếu,
`up --remove-orphans` xoá toàn bộ container giám sát (đã tái hiện trên máy demo).

Tạo secret một lần trên VM, không commit và không đưa vào GitHub:

```bash
S=/opt/booking/state
cd ~/SE2026-T29
install -m 644 deploy/observability/alertmanager/discord-webhook-url.example "$S/discord-webhook-url"
(
  umask 077
  printf '%s\n' \
    "OBS_BIND_ADDRESS=127.0.0.1" \
    "GRAFANA_ADMIN_USER=admin" \
    "GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=')" \
    "ALERTMANAGER_DISCORD_WEBHOOK_FILE=$S/discord-webhook-url" \
    > "$S/observability.env"
)
```

Ghi URL webhook Discord thật vào `discord-webhook-url` khi nhóm có kênh. File để quyền `644` vì
Alertmanager chạy bằng user `nobody`; thư mục state quyền `750` vẫn chặn user khác trên máy.

Grafana, Prometheus và Alertmanager chỉ bind `127.0.0.1` trong VM. Từ laptop, thêm SSH key của bạn
vào VM một lần, rồi mở tunnel:

```bash
multipass exec booking-demo -- bash -c 'cat >> ~/.ssh/authorized_keys' < ~/.ssh/id_ed25519.pub
ssh -N -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 ubuntu@10.97.0.43
```

Sau đó mở `http://localhost:3000`. Mật khẩu admin nằm trong `observability.env` trên VM.

Đo trên VM 2 vCPU / 4 GB ngày 15/11/2026: cả 12 container dùng khoảng 1,4 GB RAM ở 10 req/s, còn
trống khoảng 2,5 GB. Xem [kết quả đo](../evidence/observability/2026-11-15-demo-host-observability.md).
