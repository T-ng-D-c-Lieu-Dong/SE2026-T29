# VT-116 final traceability and AI usage log

This document supersedes the earlier unverified summaries. Baseline: `8fe9de89b719bde237a118e18a671db1d3dfd6cd`.
Executable backend/harness revision tested: `c3421e27c5885857dea0b14f6358954b5a80ddb1`. Later documentation/verification commits do not alter that backend/harness.
TC-03 shares an executable test with TC-01; TC-04/05 share a test; TC-17 expands to four functions. Design case count is not pytest item count.
The full suite contains 117 items; VT-116 security/state subset contains 33 items (4 unit + 13 original API + 16 correction API items).

## 1. Exact traceability

| AC/Risk | TC ID | Exact test function | Exact file | Tested commit | Evidence (`evidence/final/`) | Result |
|---|---|---|---|---|---|---|
| AC-01 | TC-01 | `test_tc01_soft_delete_happy_path` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-02 | TC-02 | `test_tc02_restore_happy_path` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 | TC-03 | `test_tc01_soft_delete_happy_path` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 | TC-04 | `test_tc04_tc05_idempotency_soft_delete_and_restore` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-02 | TC-05 | `test_tc04_tc05_idempotency_soft_delete_and_restore` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 / RISK-01 | TC-06 | `test_tc06_cross_user_soft_delete_forbidden` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 / RISK-01 | TC-07 | `test_tc07_cross_user_restore_forbidden` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 / RISK-01 | TC-08 | `test_tc08_cross_user_get_detail_isolation` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-05 | TC-09 | `test_tc09_trash_api_isolation` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-03 / INV-01 | TC-10 | `test_tc10_restore_slot_conflict_returns_409` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 | TC-12 | `test_tc12_soft_delete_not_found` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 | TC-13 | `test_auth_missing_header_returns_401` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-03 / INV-01 | TC-15 | `test_concurrent_restore_same_slot_race_condition` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-03 / INV-01 | TC-16 | `test_concurrent_booking_and_restore_same_slot` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 / OPEN RISK | TC-14 | `test_auth_header_spoofing_limitation_demonstration` | `backend/tests/integration/test_soft_delete_restore_api.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PARTIAL (spoofing reproduced) |
| AC-02 | TC-11 | `test_tc11_restore_past_booking_rejected_without_state_change` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 / AC-02 / AC-03 / AC-04 | TC-17a | `test_unit_soft_delete_success` | `backend/tests/unit/test_soft_delete_restore.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 / AC-02 / AC-03 / AC-04 | TC-17b | `test_unit_soft_delete_unauthorized` | `backend/tests/unit/test_soft_delete_restore.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 / AC-02 / AC-03 / AC-04 | TC-17c | `test_unit_restore_success` | `backend/tests/unit/test_soft_delete_restore.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 / AC-02 / AC-03 / AC-04 | TC-17d | `test_unit_restore_conflict_when_slot_rebooked` | `backend/tests/unit/test_soft_delete_restore.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 | SEC-01 | `test_private_routes_missing_identity_fail_closed` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS (4 parameters) |
| AC-04 | SEC-02 | `test_invalid_identity_is_rejected` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS (2 parameters) |
| AC-04 | SEC-03 | `test_same_customer_name_does_not_confer_ownership` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 | SEC-04 | `test_payload_owner_cannot_override_caller` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 | SEC-05 | `test_legacy_ownership_is_quarantined_even_when_identifier_is_known` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS (3 parameters) |
| AC-04 | SEC-06 | `test_unverified_historical_name_owner_is_not_claimable` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-04 / OPEN RISK | SEC-07 | `test_forged_identity_still_reads_owner_data_without_gateway_OPEN_RISK` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PARTIAL (spoofing reproduced) |
| AC-01 / AC-02 | ST-01 | `test_cancelled_delete_restore_preserves_cancellation_and_free_slot` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |
| AC-01 | ST-02 | `test_cancel_soft_deleted_booking_returns_404` | `backend/tests/integration/test_vt116_security_transitions.py` | `c3421e27c5885857dea0b14f6358954b5a80ddb1` | `09-full-pytest.log` | PASS |

## 2. Experiments outside individual test cases

| Requirement | Executable | Commit | Evidence | Result |
|---|---|---|---|---|
| Migration/quarantine | `scripts/verify_vt116_migration.py` | `c3421e2` | `08-migration.log` | PASS baseline -> 0002 -> 0003 with retained legacy row |
| One inverted business condition | `BookingService.soft_delete`, `backend/app/services/booking.py` | temporary `1b707ea` | `13-mutation.log` | KILLED: 12 fail / 21 pass; not merged |
| Line/branch coverage | `coverage run --branch --source=backend/app -m pytest backend/tests` | `c3421e2` | `10-coverage-sysmon.log`, `11-coverage-report.log`, `coverage.json` | PASS measurement; 808/859 statements, 166/200 branches |
| Time / shared state / order | `scripts/verify_vt116_flaky.py` | `0c65e34` | `14-flaky-review.log` | 33 pass each of 3 runs; no failures observed |
| NFC-01 / performance | `scripts/loadtest_vt116.py::run_load_test` | `c3421e2` | `performance-20261109T063500Z-038fb4c8.json`, `.log`, `15-performance-consistency.log` | PASS local harness; p95 420.11 ms; peak 40 |
| Paired metrics audit | `scripts/verify_vt116_performance_evidence.py` | recorded working tree in log | `15-performance-consistency.log` | PASS samples/log/JSON agree |
| Verdict correctness | `backend/tests/unit/test_loadtest_vt116.py` | `c3421e2` | `09-full-pytest.log` | 5 PASS; rejects empty/failed/slow workloads |

## 3. AI usage log (current correction session)

Tool: Codex assistant, shell/Python/pytest/Git/Docker/XeLaTeX. No external model identity is inferred for past sessions.
The earlier Antigravity narrative is a historical project assertion, not independently verified conversation evidence.

| User prompt / stage | Output actually used | Review, rejected assumption or change | Evidence |
|---|---|---|---|
| Initial request: audit assignment and PDF overflow | Compared PDF, logs, source, tests and instructions | Rejected fail-closed claim when identity absent; found clipped INV-01 and diagram | Prior audit in conversation; retained original PDF backup |
| FINAL CORRECTION, SECURITY -> TEST/EVIDENCE -> PERFORMANCE -> README -> LATEX/PDF -> GITHUB | Wrote scoped correction plan before production patch | Rejected header presence as authentication; rejected legacy UUID secrecy and name ownership | `final-correction-plan.md`; commit `a1a7be6`; `01-security-red.log` |
| Require missing-identity, cross-user, name-collision and legacy negative tests | Added `test_vt116_security_transitions.py`, identity dependency and quarantine migration | Model flag needed because prefix-only quarantine missed historical name owners; all old rows disabled by migration | `03-historical-owner-red.log`; security diff `aed7866`; `08-migration.log` |
| Complete cancelled/past transitions | Real API tests for TC-11, cancelled delete/restore, deleted cancel | Corrected TC-11 from an unexecuted unit claim to a real API test | `09-full-pytest.log`, `14-flaky-review.log` |
| Reconcile measurements and collect valid coverage | Paired run ID, raw latency samples, peak lifecycle/HTTP counters; sysmon coverage | Semaphore is only a cap; exclude warmup duration; failed workloads cannot pass p95 verdict | `05-performance-verdict-red.log`, `07-performance-verdict-green.log`, `10-coverage-sysmon.log`, `15-performance-consistency.log` |
| Preserve genuine failures | Kept sandbox socket failure and floating point assertion failure | Socket denial is not business RED; numeric test uses approximate float comparison | Historical commits `a1a7be6` (sandbox denial), `56ec750` (float assertion); redundant local logs removed |
| Run one mutation and flaky checks | Temporary guard inversion; reverse-order/timezone runs | One mutation killed does not imply mutation coverage; bounded repetition does not prove flake freedom | `13-mutation.log`, `14-flaky-review.log` |
| Correct PDF and reflection | Updated evidence-backed report and marked reflection as draft | No invented student experience, sign-off, historical prompt quotation, or production safety claim | Report, PDF QA evidence and final acceptance file |

## 4. Two plausible but unreliable AI outputs

1. A nonempty `X-User-Id` looks like authentication but is just an assertion. Missing identity is now rejected; direct spoofing is still reproducible. Only a trusted ingress that strips client headers and injects verified identity can close this gap.
2. An identifier `legacy_<UUID>` looks difficult to guess but may be derived from exposed IDs. A new DB access flag defaults false for historical rows; knowing any old owner string cannot re-enable access. The original migration comment calling it unguessable is historical wording, not the security mechanism.

## 5. Limits

No signed human approval, academic commitment or reflection authorship is inferred from AI output. No browser E2E, IdP, real network HTTP load, production topology or deterministic forced DB interleaving has been proved. `asyncio.gather` plus DB count assertions demonstrates observed outcomes, but does not prove every constraint rollback path was exercised.
