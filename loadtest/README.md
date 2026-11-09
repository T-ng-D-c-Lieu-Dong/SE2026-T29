# Load Testing — K6 Suite

Thư mục `loadtest/` chứa bộ công cụ và các kịch bản kiểm thử tải (Load Testing) bằng [k6](https://k6.io/) cho hệ thống Booking API, phục vụ kiểm chứng mốc **M6 — Reliability Demo** và chỉ số cam kết **E15** trong [Evidence](../docs/evidence.md).

---

## 1. Mục tiêu và tiêu chuẩn đánh giá (SLO & E15)

- **Cam kết E15:** Dưới mức tải tham chiếu 10 request/giây trong 10 phút, độ trễ p95 của các endpoint nghiệp vụ phải đạt dưới **500 ms**, tỷ lệ lỗi HTTP 5xx phải dưới **1%**.
- **Kịch bản kiểm thử:**
  - `slots.js`: Kiểm thử tải endpoint tra cứu khung giờ trống (`GET /api/slots`).
  - `booking.js`: Kịch bản tổng hợp xem slot → đặt (`201`) → hủy (`204`), kèm tải chỉ đọc. Chỉ hủy ID do chính lượt chạy tạo ra. Tranh chấp slot (`409`) được đếm riêng, không hủy booking của người khác.

---

## 2. Cấu trúc thư mục

```text
loadtest/
├── README.md         # Tài liệu hướng dẫn cấu hình và chạy thử tải
├── booking.js        # Kịch bản k6 tổng hợp quy trình tra cứu và đặt lịch
├── slots.js          # Kịch bản k6 kiểm thử endpoint tra cứu slot (/api/slots)
└── tests/booking.test.mjs # Kiểm thử hành vi với HTTP giả lập bằng Node.js
```

---

## 3. Cài đặt k6

### Cách 1: Cài đặt k6 CLI trực tiếp

- **Windows (winget):**
  ```powershell
  winget install k6 --source winget
  ```
- **Windows (Chocolatey):**
  ```powershell
  choco install k6
  ```
- **macOS (Homebrew):**
  ```bash
  brew install k6
  ```
- **Linux (Debian/Ubuntu):**
  ```bash
  sudo gpg -k
  sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
  echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
  sudo apt-get update && sudo apt-get install k6
  ```

### Cách 2: Sử dụng Docker container (không cần cài đặt CLI)

```bash
docker run --rm -i grafana/k6 run - < loadtest/slots.js
```

---

## 4. Các biến môi trường cấu hình

| Biến | Ý nghĩa | Mặc định | Ví dụ |
| --- | --- | --- | --- |
| `BASE_URL` | Địa chỉ gốc của Booking API | `http://localhost:8000` | `http://192.168.1.100:8000` |
| `TARGET_DATE` | Ngày cần tra cứu slot (`YYYY-MM-DD`) | Ngày mai (tính theo ngày hiện tại) | `2026-11-01` |
| `VUS` | Số VU, chỉ dùng cho `slots.js` | `5` | `10` |
| `DURATION` | Thời lượng: `slots.js` / `booking.js` | `30s` / `10m` | `15s` |
| `TARGET_RPS` | Tổng HTTP request/giây mục tiêu của `booking.js` | `10` | `5` |
| `PRE_ALLOCATED_VUS` | VU cấp sẵn cho **mỗi** scenario của `booking.js` | `10` | `5` |
| `MAX_VUS` | VU tối đa cho **mỗi** scenario, ≥ `PRE_ALLOCATED_VUS` | `50` | `20` |
| `SUMMARY_PATH` | Đường dẫn JSON kết quả `booking.js`; tạo thư mục cha trước | `reports/loadtest-booking-summary.json` | `reports/e15.json` |
| `BOOKING_RELEASE` | Release đang chạy, ghi vào metadata | `unspecified` | `v0.2.0` |
| `BOOKING_COMMIT_SHA` | SHA của backend đang đo | `unspecified` | `abc1234` |
| `TEST_ENVIRONMENT` | CPU/RAM, OS, Docker, cấu hình máy API và máy tạo tải | `unspecified` | `demo VM: 2 CPU, 4 GB RAM, Ubuntu` |
| `DATASET` | Số booking ban đầu, ngày và điều kiện dữ liệu | `unspecified` | `0 booking, ngày thử riêng` |

---

## 5. Hướng dẫn thực thi

### 5.1. Chạy nhanh kịch bản kiểm tra tra cứu slots (`slots.js`)

```bash
# Sử dụng CLI cục bộ
k6 run loadtest/slots.js

# Hoặc truyền biến môi trường tuỳ chỉnh
k6 run -e BASE_URL=http://localhost:8000 -e VUS=5 -e DURATION=30s loadtest/slots.js
```

### 5.2. Chạy qua Docker kết nối vào backend host

- **Windows / macOS (qua host.docker.internal):**
  ```bash
  docker run --rm -i -e BASE_URL=http://host.docker.internal:8000 grafana/k6 run - < loadtest/slots.js
  ```
- **Linux (qua host network):**
  ```bash
  docker run --rm -i --network=host -e BASE_URL=http://localhost:8000 grafana/k6 run - < loadtest/slots.js
  ```

### 5.3. Xuất kết quả tổng hợp (Summary JSON) để lưu evidence

```bash
k6 run --summary-export=reports/loadtest-slots-summary.json loadtest/slots.js
```

### 5.4. Chạy profile tổng hợp của tuần 2 (`booking.js`)

Từ thư mục gốc repository, chạy nhanh trước bằng PowerShell:

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
k6 run -e DURATION=15s loadtest/booking.js
```

Chạy đủ profile 10 phút và lưu điều kiện đo:

```powershell
$version = Invoke-RestMethod http://localhost:8000/api/version
k6 version | Out-File reports/k6-version.txt
k6 run -e BASE_URL=http://localhost:8000 `
  -e BOOKING_RELEASE=$($version.release) -e BOOKING_COMMIT_SHA=$($version.commit_sha) `
  -e 'TEST_ENVIRONMENT=Điền CPU/RAM/OS/Docker và máy tạo tải thực tế' `
  -e 'DATASET=Điền số booking ban đầu và ngày thử thực tế' `
  loadtest/booking.js
```

Qua Docker (PowerShell, Windows/macOS), mount cả thư mục để resolve `./slots.js` và lưu JSON:

```powershell
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:2.3.0 run `
  -e BASE_URL=http://host.docker.internal:8000 loadtest/booking.js
```

Profile dùng hai scenario `constant-arrival-rate`: 20 lượt đọc mỗi 5 giây (4 request/giây),
và 10 lượt xem–đặt–hủy mỗi 5 giây (2 lượt × 3 request = 6 request/giây).
Tổng mục tiêu là **10 HTTP request/giây**, khoảng **6.000 request trong 10 phút**;
không đặt `rate=10` cho luồng ba request rồi gọi đó là 10 request/giây.
Không `sleep` trong các scenario này; executor tự điều tiết tải.

Nếu hết slot, lỗi hoặc gặp `409`, luồng dừng sớm nên số request thực tế có thể thấp hơn mục tiêu.
Đối chiếu `http_reqs.values.count/rate`, `dropped_iterations`, `booking_conflicts` và thời gian đo;
không công nhận E15 chỉ vì thresholds xanh khi tải thực tế thiếu.
Mỗi request timeout 10 giây; cho phép luồng đang chạy hoàn tất tối đa 45 giây sau thời lượng cấu hình.
Hủy lỗi hoặc ngắt cưỡng bức có thể để lại booking thử; dùng ngày thử riêng và kiểm tra dữ liệu sau chạy.

`handleSummary` tự ghi `SUMMARY_PATH` gồm metrics, kết quả từng threshold và metadata
(URL, ngày, profile, release/SHA, môi trường, dataset). Console vẫn in số request, rate,
p95 và các threshold thất bại. File kết quả nằm trong `reports/` được Git bỏ qua;
sao chép kết quả đo thật cần chia sẻ sang `docs/evidence/` kèm log và cấu hình máy.
Lần chạy ngắn dùng để kiểm tra script; E15 cần đủ 10 phút trên môi trường tham chiếu.

---

## 6. Tiêu chí kiểm tra trong kịch bản (Thresholds & Checks)

Mỗi kịch bản k6 tích hợp các ngưỡng kiểm tra chất lượng tự động:

- **HTTP Status Check:** Xem slot trả `200`, tạo trả `201` hoặc `409` do tranh chấp, hủy trả `204`. Các mã ngoài hợp đồng, timeout và lỗi kết nối đều làm tăng `http_req_failed`.
- **Response Format Check:** Dữ liệu trả về phải là mảng JSON hợp lệ chứa các slot có trường `starts_at`.
- **Threshold `http_req_duration`:** `p(95) < 500ms` (đáp ứng tiêu chí E15).
- **Threshold `http_req_failed`:** `rate < 0.01` (tỷ lệ request lỗi không vượt quá 1%).
- **Riêng `booking.js`:** p95 < 500 ms cho từng route; `http_server_errors < 1%` chỉ tính 5xx;
  checks > 99%; có ít nhất một lượt đặt–hủy thành công; `dropped_iterations == 0`.
  `409` không bị tính thành 5xx hay lỗi HTTP ngoài dự kiến, được lưu trong `booking_conflicts`.

## 7. Kiểm tra script

```bash
node --experimental-vm-modules --test loadtest/tests/booking.test.mjs
python -m pytest -c pytest.ini backend/tests/unit/test_loadtest.py
k6 inspect loadtest/booking.js
```

Node tests chạy các module thật với HTTP/metrics giả lập để kiểm tra luồng thành công,
409, 5xx, dữ liệu sai, cấu hình tải và summary. Chúng không đo hiệu năng backend.

Tham chiếu: [constant-arrival-rate](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/),
[custom summary](https://grafana.com/docs/k6/latest/results-output/end-of-test/custom-summary/).

## 8. Chạy trên máy demo qua GitHub Actions (C085)

Chọn **Actions → Load Test on Demo Host → Run workflow**, branch `main`.
Mặc định 10 request/giây trong 10 phút; có lựa chọn 30 giây để kiểm tra nhanh.
Điền dataset và dùng ngày thử riêng. Workflow chạy thủ công trên `[self-hosted, demo]`,
qua web `http://localhost` port 80; không gọi port 8000 trên host.
Artifact luôn có summary, log, version, thông tin máy và manifest/history hiện tại,
kể cả khi k6 trả lỗi do vượt ngưỡng.

Workflow giữ runner trong suốt phép đo. Nếu chỉ có một runner, chạy tải từ terminal/máy
khác khi diễn tập cần deploy/rollback đồng thời. Xem
[release drill và evidence](../docs/releases/drill-release.md).
