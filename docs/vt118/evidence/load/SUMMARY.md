# VT-118 load experiment — 60 concurrent workers × 10 POST /api/appointments per scenario

Generated 2026-11-07T16:27:54+00:00 from the JSON files in this folder (`loadtest/vt118/run_all.sh`).

- Environment: one cloud container, **2 vCPU / 7 GB RAM**, client + uvicorn (1 worker, như Dockerfile) + PostgreSQL 16.15 trên cùng máy, kết nối loopback; không có nginx.
- Code: `baseline` = commit 5c8efc2 (main); `after` = submission branch; `variant-commit-then-refresh` = submission branch with only the order of `commit()`/`refresh()` reverted (temporary branch `tmp/vt118-variant-commit-then-refresh` @ 3fc0692, not merged) to test plan review R2.
- Notifier: `default` = LoggingBookingNotifier; `ok` returns immediately; `fail` raises ConnectionError; `hang` never returns (cut by the 0.5 s timeout).
- p95 = nearest-rank over 600 requests per run; peak in-flight = 60 in every run.

| Scenario (code · notifier · payload) | Runs | p50 (s) | p95 (s) per run | max (s) | Status codes | notification_status | p95 ≤ 2.0 s | 0×5xx | rows = 201 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline-default-valid | 3 | 0.128 | 0.626 / 0.622 / 0.622 | 1.584 | {'201': 1800} | {'<missing>': 1800} | yes | yes | yes |
| baseline-default-valid-100 | 1 | 0.151 | 0.491 | 1.277 | {'201': 600} | {'<missing>': 600} | yes | yes | yes |
| baseline-default-oversized-1mb | 1 | 0.449 | 0.761 | 0.834 | {'422': 600} | - | yes | yes | yes |
| after-default-valid | 3 | 0.209 | 0.296 / 0.293 / 0.331 | 0.530 | {'201': 1800} | {'sent': 1800} | yes | yes | yes |
| after-ok-valid | 1 | 0.171 | 0.301 | 0.473 | {'201': 600} | {'sent': 600} | yes | yes | yes |
| after-fail-valid | 3 | 0.193 | 0.291 / 0.263 / 0.307 | 0.496 | {'201': 1800} | {'failed': 1800} | yes | yes | yes |
| after-hang-valid | 3 | 0.524 | 0.754 / 0.762 / 0.747 | 0.850 | {'201': 1800} | {'timeout': 1800} | yes | yes | yes |
| after-ok-valid-100 | 1 | 0.201 | 0.260 | 0.438 | {'201': 600} | {'sent': 600} | yes | yes | yes |
| after-ok-oversized-1mb | 3 | 0.487 | 0.809 / 0.831 / 0.832 | 1.310 | {'422': 1800} | - | yes | yes | yes |
| variant-commit-then-refresh-ok-valid | 1 | 0.140 | 0.667 | 1.450 | {'201': 600} | {'sent': 600} | yes | yes | yes |
| variant-commit-then-refresh-hang-valid | 3 | 1.499 | 3.033 / 3.043 / 3.023 | 3.526 | {'201': 1662, '500': 138} | {'timeout': 1662} | **NO** | **NO** | yes |

Server-side cause of the 138 HTTP 500 in the variant (from `*.server.log`, not committed):

```
variant-commit-then-refresh-hang-valid.server.log: 48 × TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 3
variant-commit-then-refresh-r2-hang-valid.server.log: 45 × TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 3
variant-commit-then-refresh-r3-hang-valid.server.log: 45 × TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 3
```
