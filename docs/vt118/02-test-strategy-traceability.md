# VT-118 — Test strategy, test cases, traceability và AI usage log

## 1. Test strategy dựa trên risk

| Mức | Dùng để chứng minh | Test |
| --- | --- | --- |
| Unit (fake repository/notifier, không DB) | Phân loại outcome theo từng lớp hành vi của notifier; thứ tự commit → notify; không ghi PII vào log; `CancelledError` không bị nuốt; ràng buộc cấu hình | TC01–TC07, TC17, TC18, TC20, TC21 |
| Integration/API (httpx ASGI + PostgreSQL 16 thật) | Booking thật sự được lưu cho mọi outcome; không giữ connection khi notify; 409/422/500 không phát thông báo; đầu vào lớn bị chặn sớm; contract của response | TC08–TC16, TC19, TC22 |
| Tải (uvicorn + PostgreSQL, 60 worker) | NFR1: p95 ≤ 2.0 s, 0 lỗi 5xx khi notifier ok/lỗi/treo và khi payload 1 MB | LT1 (`loadtest/vt118/`) |
| E2E (Playwright UI) | **Không cần cho slice này.** UI không đọc `notification_status` (field chỉ được thêm vào, `frontend/src/types.ts` không bị ảnh hưởng), và risk nằm ở backend. Luồng đặt lịch trên UI đã có `frontend/e2e/booking.spec.ts`. Một E2E mới chỉ kiểm tra lại React mà không chạm vào risk. | — |
| Không cần | Contract test với nhà cung cấp email/SMS thật (chưa có kênh thật); migration test (không đổi schema); test tải dài hạn (E15 đã có kịch bản k6 riêng) | — |

## 2. Equivalence partitioning — cách chọn test data

| Miền đầu vào/đầu ra | Lớp tương đương | Đại diện được chọn | Test |
| --- | --- | --- | --- |
| Hành vi notifier | N1 hoàn tất bình thường | trả về ngay | TC01, TC04[N1], TC08, TC22 |
| | N2 ném `Exception` | `ConnectionError` có PII trong message | TC02, TC04[N2], TC09, TC16 |
| | N3 không xong trong ngân sách | chờ `asyncio.Event()` không bao giờ set | TC03, TC04[N3], TC07, TC10 |
| | N4 chặn event loop (ngoài hợp đồng async) | `time.sleep(0.3)` | TC18 (xfail, residual risk) |
| `customer_name` sau strip | L1 1..100 ký tự (hợp lệ) | `"Cuong"`, biên `"C"`, biên 100 ký tự | TC08, TC14a, TC14b |
| | L2 rỗng (không hợp lệ) | `"   "` | TC14c |
| | L3 > 100 ký tự (không hợp lệ) | 101 ký tự (biên); 1 000 000 ký tự ≈ 1 MB (lớp con "đầu vào lớn" của risk) | TC14d, TC13, TC19, LT1 |
| Kết quả request | 201 / 409 / 422 / 500 | slot trống / slot đã đặt / phút 15 hoặc tên sai / fault injection | TC08, TC12, TC05 + TC13, TC06 + TC15 |
| `BOOKING_NOTIFICATION_TIMEOUT_SECONDS` | ≤ 0 / (0, 5] / > 5 | 0, −1 / 0.001, 5.0 / 5.01, 60 | TC17 |
| Đầu ra `notification_status` | `sent` / `failed` / `timeout` | mỗi lớp đầu ra có ít nhất 1 API test | TC08, TC09, TC10 |

Mỗi lớp chỉ cần **một đại diện** vì mọi giá trị trong lớp đi cùng một nhánh code. Ví dụ, mọi lớp con của
`Exception` đều vào cùng nhánh `except Exception`. Riêng `customer_name`, test thêm giá trị biên 1/100/101,
vì `max_length = 100` của schema là lớp chặn chính cho risk đầu vào lớn. Kích thước 1 MB được chọn vì đó
là giới hạn mặc định của nginx ở production, và vì cổng 8000 ở `deploy/compose.yaml` bỏ qua lớp nginx này.
Ý tưởng chia lớp theo **đầu ra** là để mỗi phần tử của bảng mapping đều được một test quan sát, nhờ đó
mutation "đổi mapping" bị phát hiện.

## 3. Bảng test case

| ID | Risk / requirement | Mức | Precondition / input | Expected | Ưu tiên |
| --- | --- | --- | --- | --- | --- |
| TC01 | AC1 | Unit | notifier N1, appointment +07:00 | `DELIVERED`; 1 event đúng id/tên/`starts_at` UTC | P1 |
| TC02 | AC2, NFR3 (failure-path) | Unit | notifier N2, message chứa tên khách | `FAILED`; log `booking.notification.failed` có id + `ConnectionError`; không có tên, không `exc_info` | P1 |
| TC03 | AC3, risk timeout (failure-path) | Unit | notifier N3, timeout 0.05 s | `TIMED_OUT`, < 1 s, log `timed_out` | P1 |
| TC04 | Invariant, NFR2 | Unit | N1/N2/N3 qua `create_and_notify` | booking `booked`, 1 commit, `calls[-2:] == [commit, notify]` | P1 |
| TC05 | AC4 (negative) | Unit | slot phút 15 | `InvalidSlot`, 0 event, 0 commit | P2 |
| TC06 | AC4 (negative) | Unit | fault injection `error` | `InjectedBookingFault`, 0 event | P2 |
| TC07 | Contract | Unit | hủy task ngoài khi notifier treo | `CancelledError` được truyền đi | P2 |
| TC08–TC10 | AC1–AC3 | API | N1/N2/N3, timeout 0.2 s | 201; `sent`/`failed`/`timeout`; row `booked`; 1 event khớp id | P1 |
| TC11 | NFR2 | API | notifier đo pool khi được gọi | `pool.checkedout() == 0`, row đã thấy từ session khác | P1 |
| TC12 | AC4 (negative) | API | đặt cùng slot 2 lần | 201 rồi 409; đúng 1 event | P1 |
| TC13 | AC5, risk đầu vào lớn (negative) | API | `customer_name` 1 000 000 ký tự | 422 trong < 1 s; 0 row; 0 event | P1 |
| TC14a–d | AC5, biên EP | API | 1, 100 (hợp lệ); `"   "`, 101 (không hợp lệ) | 201 + `sent` + tên nguyên vẹn / 422 + 0 event | P2 |
| TC15 | AC4 (negative) | API | fault injection `error` | 500; 0 event; 0 row | P2 |
| TC16 | Invariant dưới đồng thời | API | 60 POST đồng thời, notifier N2 | 60 × 201 `failed`; 60 row | P2 |
| TC17 | AC3 (config) | Unit | 0, −1, 0.001, 5, 5.01, 60 | hợp lệ chỉ trong (0, 5]; mặc định 0.5 | P3 |
| TC18 | Residual risk | Unit (xfail) | notifier `time.sleep(0.3)`, timeout 0.05 s | xfail: timeout không cắt được | P3 |
| TC19 | Residual risk đầu vào lớn | API (xfail) | 1 MB | xfail: response 422 ≈ 1 MB | P3 |
| TC20 | Invariant (review F2) | Unit | appointment `starts_at=None` | `FAILED`, không ném lỗi | P1 |
| TC21 | AC1 production wiring (review F1) | Unit | `create_app()` + notifier mặc định | 1 dòng JSON INFO + 1 WARNING; không có tên | P2 |
| TC22 | Contract response (mutation M5) | API | booking hợp lệ | mọi field của response = row đã lưu, `cancelled_at = null` | P1 |
| LT1 | NFR1 | Tải | 60 worker × 10 request, 6 kịch bản | p95 ≤ 2.0 s, 0 × 5xx, số row = số 201 | P1 |

## 4. Traceability

| Acceptance criterion / risk | Test case | Test file | Commit | Kết quả (evidence) |
| --- | --- | --- | --- | --- |
| AC1 gửi đúng 1 event, `sent` | TC01, TC08, TC21, TC22 | unit + integration | `dac0952` → `6a34476`, `d93b5df`, `9065503` | đỏ (04) → xanh (07) |
| AC2 lỗi kênh → 201 + `failed`, log không PII | TC02, TC09, TC16 | unit + integration | `dac0952` → `6a34476` | đỏ (04) → xanh (05, 07); giết M1, M3 |
| AC3 timeout → 201 + `timeout` | TC03, TC10, TC17 | unit + integration | `dac0952` → `6a34476` | đỏ (04) → xanh; giết M2 |
| AC4 không thông báo khi 409/422/500 | TC05, TC06, TC12, TC15 | unit + integration | `dac0952` | guard xanh trước/sau; TC12 đỏ (04) vì chưa gửi event cho booking đầu |
| AC5 đầu vào lớn bị chặn, biên 100 | TC13, TC14a–d | integration | `dac0952` | guard xanh; TC14a/b đỏ (04) → xanh |
| Invariant (commit trước, không 5xx) | TC04, TC07, TC11, TC20 | unit + integration | `dac0952`, `2e27ae3` → `d93b5df` | TC20 đỏ (06) → xanh (07) |
| NFR1 p95 ≤ 2.0 s ở 60 đồng thời | LT1, TC16 | `loadtest/vt118/*` | `23152a7` | `load/SUMMARY.md`: sau patch p95 ≤ 0.83 s; biến thể AI plan p95 3.03 s + 138 × 500 |
| NFR2 không giữ connection | TC04, TC11, LT1 biến thể | unit + integration + tải | `6a34476` | xanh; biến thể `commit → refresh` hỏng ở tải |
| NFR3 log không PII | TC02, TC21 | unit | `6a34476`, `d93b5df` | xanh |
| Risk: notifier chặn loop; 422 echo 1 MB | TC18, TC19 | unit + integration | `dac0952` | xfail strict (residual risk) |

Commit trên nhánh `feat/vt118-booking-notification-23001840`: `aad4653` spec/plan/harness → `dac0952` test-first →
`ec5c08b` stub (đỏ đúng lý do) → `6a34476` patch AI → `2e27ae3` test lỗi review → `d93b5df` sửa review →
`9065503` TC22 sau mutation → `4f06aa9` mutation/coverage/flaky → `23152a7` tải → commit tài liệu cuối.

## 5. AI usage log

| # | Công cụ | Prompt chính | Output được dùng | Thay đổi / bác bỏ | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | Claude (Cowork), agent `Plan` chỉ đọc repo | nguyên văn trong `ai-plan-v1.md` | chọn `appointment.created`; `except Exception` không bắt `CancelledError`; stub trước khi tính red; không dùng BackgroundTasks; đo baseline trước | bác bỏ queue + worker (R1), k6 + env fault (R4); sửa thứ tự `commit → refresh` (R2), giả định nginx (R3), ngưỡng thời gian chặt (R5) | `01-plan-review-experiments.log`, `load/SUMMARY.md` |
| 2 | Claude (Cowork), phiên chính | đề bài VT-118 + "cho AI viết test trước implementation" + spec ở `01-spec-plan-review.md` | 2 file test (TC01–TC19), harness tải, script thí nghiệm | TC21 sửa cách chọn handler (pytest 9); thêm TC20–TC22 sau review và mutation | `03`, `04`, `06`, `09`, `10` |
| 3 | Claude (Cowork), agent `general-purpose` | "tạo PATCH NHỎ thay các stub để test pass; chỉ sửa 8 file production; không chạy test, không commit" | toàn bộ patch `6a34476` | giữ phần lớn; sửa F1 (logger không có handler) và F2 (map event ngoài khối `try`) | `05`, `06`, `07` |
| 4 | Claude (Cowork), phiên chính | "tạo mutant đổi mapping response field, đo coverage, kiểm tra flaky, chạy tải 60 đồng thời" | patch mutant, `run_mutations.sh`, `coveragerc`, lệnh flaky, ma trận tải | sửa lỗi `sed` của runner; thêm cấu hình greenlet cho coverage | `08`–`12`, `load/` |
| 5 | Claude (Cowork), phiên chính | "soạn báo cáo PDF" | bản nháp báo cáo và reflection | sinh viên đọc lại, chỉnh giọng văn và tự chịu trách nhiệm | PDF nộp bài |

Không dùng câu "AI nói đúng" làm bằng chứng. Mọi kết luận ở trên đều có lệnh chạy và log đi kèm.
