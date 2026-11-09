# VT-116 final risk-based test strategy

## Specification (five ACs)

Problem: implement non-destructive appointment soft deletion/restoration while preserving slot consistency and isolating private records by asserted ownership.

- **AC-01:** Owner soft-delete returns 200, sets deletion timestamp, preserves the row, hides it from normal list/detail (list excludes it; detail 404), and releases a booked slot. Repeated delete is 200 and preserves the original timestamp.
- **AC-02:** Owner restores a future deleted record, clearing deletion fields (200). Repeated restore is 200. Cancelled records retain cancellation status/timestamp and do not reclaim a slot. Past-slot restore is rejected (422), state unchanged.
- **AC-03:** Restoring a booked record into an occupied slot returns 409. Concurrent restore/restore or create/restore leaves one active booking per slot, with one success and one 409 in the observed experiments.
- **AC-04:** All private booking routes require a valid asserted identity (missing/blank/reserved/oversized identity 401). Cross-user detail is 404, writes 403; list filters owner. Same customer name confers no rights. Historical access-disabled rows remain hidden/immutable even when their owner string is known. A forged valid identity remains an OPEN authentication risk without trusted ingress.
- **AC-05:** Trash requires identity and returns only that owner's enabled, deleted records.

NFC-01: 40 concurrent tasks, lifecycle p95 <=1.5 s, scope explicitly local in-process harness. NFC-02: transactional PostgreSQL writes and partial unique index for `(starts_at)` where booked and not deleted. NFC-03: no public patient data read without identity; retain historical rows pending verified reassignment.

INV-01 (load-bearing consistency contract): at most one active booked, undeleted appointment per starts_at. INV-02: private API authorization is fail-closed at identity boundary under an asserted trusted-upstream identity, not a proof of authentication. INV-03: soft-delete retains row and cancellation metadata; historical access is disabled by migration.

## Levels, data and exclusions

Unit tests isolate service guards using a fixed injected clock. API integration tests use real PostgreSQL with a separate session per request and cleanup before each case. API E2E through router/service/repository is covered; browser E2E is deferred because no soft-delete/restore UI exists. Do not add browser happy paths to infer authorization or IdP correctness. No tests of external IdP internals are meaningful here; actual ingress integration is the highest-priority future test.

Data: distinct asserted owners Alice/Bob, plus identical display names to detect ownership confusion; distinct future slots 3-30 days away on half-hour boundaries; fixed past date 2020 for TC-11; same-slot records for conflict/race; known legacy strings and old name owners with access flag false. No patient data or shared database is used. UUIDs distinguish rows, never authorize callers.

## State transitions

S1=booked,not-deleted; S2=cancelled,not-deleted; S3=booked,deleted; S4=cancelled,deleted. RESTORED is a transition, not a separate state.

| Transition | Start/action/guard | End / result | Executable evidence |
|---|---|---|---|
| T1 | S1/delete/owner | S3, 200, slot released | TC-01 |
| T2 | S1/cancel/owner | S2, 204 | original cancel regression; ST-01 |
| T3 | S3/restore/owner, future, free | S1, 200 | TC-02 |
| T4 | S3/restore/occupied slot | S3, 409 | TC-10 |
| T5 | S3/restore/past | S3, 422, timestamp retained | TC-11 |
| T6 | S2/delete/owner | S4, 200 | ST-01 |
| T7 | S4/restore/owner, future | S2, 200, cancellation unchanged even if slot rebooked | ST-01 |
| T8 | S3/delete/owner | S3, 200, timestamp retained | TC-04 |
| T9 | S1/restore/owner | S1, 200 | TC-05 |
| T10 | S1/delete/other owner | S1, 403 | TC-06 |
| T11 | S3/restore/other owner | S3, 403 | TC-07 |
| T12 | S3/cancel/valid identity | S3, 404 | ST-02 |

All twelve listed transitions now have executable checks. This is coverage of the selected table, not every possible combination of state, identity, time, gateway and DB scheduling.

## Test case matrix

| ID | AC/Risk | Level | Precondition/input | Expected | Priority |
|---|---|---|---|---|---|
| TC-01 | AC-01 | API | Alice owns booked future slot; delete, Bob books it | 200; deleted; Bob 201 | P0 |
| TC-02 | AC-02 | API | Alice deleted booking, future free slot | 200; deletion cleared; detail visible | P0 |
| TC-03 | AC-01 | API | Deleted booking, normal detail read | 404 | P0 |
| TC-04 | AC-01 | API | Repeat owner delete | 200, original deleted_at | P1 |
| TC-05 | AC-02 | API | Repeat owner restore on active | 200, active | P1 |
| TC-06 | AC-04/RISK-01 | API negative | Bob deletes Alice's booking | 403 | P0 |
| TC-07 | AC-04/RISK-01 | API negative | Bob restores Alice's deleted booking | 403 | P0 |
| TC-08 | AC-04/RISK-01 | API negative | Bob reads Alice's detail | 404 | P0 |
| TC-09 | AC-05 | API | Alice/Bob each have deleted booking | Alice's trash only Alice's booking | P0 |
| TC-10 | AC-03 | API failure | Deleted Alice booking; Bob rebooks same slot | Restore 409; no overwrite | P0 |
| TC-11 | AC-02 | API failure | Deleted booking's slot moved into past fixture | 422; remains deleted, timestamp retained | P1 |
| TC-12 | AC-01 | API negative | Delete nonexistent UUID | 404 | P1 |
| TC-13 | AC-04 | API negative | Delete/restore/trash lack identity | 401 | P0 |
| TC-14 | OPEN RISK | API characterization | Client forges Alice's valid header | 200 observed; spoofing NOT blocked | P0 |
| TC-15 | AC-03/INV-01 | API concurrency | Two different deleted bookings, same slot; restore both | 200+409; one active DB row | P0 |
| TC-16 | AC-03/INV-01 | API concurrency | Create and restore concurrently on same slot | one 201/200 and one 409; one active | P0 |
| TC-17a-d | AC-01..04 | Unit | Fixed clock, authorized/unauthorized delete, restore/conflict | Correct state/domain errors | P0 |
| SEC-01 | AC-04 | API negative | Missing identity: create/list/detail/cancel | 401 in four parameterized items | P0 |
| SEC-02 | AC-04 | API negative | Blank or >100-character identity | 401 in two items | P0 |
| SEC-03 | AC-04 | API | Same customer_name, different asserted owners | Bob list excludes Alice; detail404/cancel403 | P0 |
| SEC-04 | AC-04 | API negative | Body owner_id differs from asserted caller | 422 | P0 |
| SEC-05 | AC-04 | API negative | Known legacy_/anonymous/unassigned owners | 401 reserved caller; valid caller cannot read row | P0 |
| SEC-06 | AC-04 | API negative | Known old name owner, access flag false | list empty; detail404; writes403 | P0 |
| SEC-07 | OPEN RISK | API characterization | Forged current owner's header on detail | 200 observed; direct access remains unsafe | P0 |
| ST-01 | AC-01/02 | API | Cancel -> delete -> Bob rebooks -> restore | cancellation/timestamp retained; Bob slot not reclaimed | P0 |
| ST-02 | AC-01 | API negative | Cancel soft-deleted booking | 404 | P1 |

Exact functions/files/commits/results: `traceability-and-ai-log.md`. AC-04 is PARTIAL overall: local authorization checks pass, actual authentication and anti-spoofing are not implemented. AC-01/02/03/05 have checks for the selected behaviors, not a universal correctness proof.

## Quality interpretation

One owner-comparison mutation was killed (12 fail, 21 pass) on temporary commit 1b707ea; no mutation remains in the submitted branch. Full code suite: 117 pass; a claim of 96 tests from historical evidence is withdrawn. Coverage: 94.06% statements, 83.00% branches for backend/app; repository branch coverage is only 60%, leaving useful future work around error/fallback paths. The old exit-139 cause is unverified; final sysmon measurement succeeds.

Three 33-item runs varied timezone and reversed order, with no failure. Unit clocks are fixed and API slots are safely in the future. Cleanup isolates serial tests but does not make the shared test DB safe for pytest-xdist or simultaneous harness/test execution. Concurrent requests are observed through asyncio.gather, not a deterministic barrier forcing both transactions past their precheck; rollback-path saturation remains unproved.

Performance: cap40, observed peak40, 200 lifecycles/600 requests, 0 errors, p95 420.11ms; in-process ASGI with real PostgreSQL, excluding warmup. Real network/gateway/production capacity remains NOT VERIFIED.
