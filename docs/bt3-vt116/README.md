# BT3 - VT-116 - Nguyễn Việt Anh (23001827)

APP-03 / SE2026-T29. Personal branch: `bt3/23001827-vt116-soft-delete-restore`.
Baseline: `8fe9de89b719bde237a118e18a671db1d3dfd6cd`. No merge into main.
See `final-acceptance.md` for remote verification and final status; never infer a push from a local branch name.

## Contract and identity boundary

Public: `/api/slots`, `/health/live`, `/health/ready`, `/api/version` (slot response exposes availability, not patient records).
Private: **all** `/api/appointments` routes, including POST create, GET list/detail/trash, PATCH soft-delete/restore and DELETE cancel.
They require a nonempty, <=100-character `X-User-Id`; reserved `legacy_*`, `anonymous`, `unassigned` callers are rejected (401).
Ownership is an upstream assertion, **not authenticated by this backend**. Direct forged headers still succeed for current enabled owners: negative characterization tests intentionally document OPEN RISK. Before public deployment, trusted ingress must strip client identity headers, validate tokens, inject identity and deny direct backend access. That ingress is not implemented here.

Create uses the asserted caller only; a conflicting body `owner_id` returns 422. `customer_name` is display data, never identity evidence. Cross-user detail returns 404; cross-user writes return 403.

### Intentional compatibility/migration impact

Existing frontend, smoke/persistence clients and callers that omit identity now receive 401 on private routes. They must obtain identity through trusted ingress; hardcoding a name or adding a free-form browser header is not a security fix. Existing business regression tests explicitly supply a caller, retaining their original business assertions. Public slots/health/version remain accessible.
Run Alembic `upgrade head` before deployment. Revision `20261109_0003` sets `owner_access_enabled=false` for **all pre-existing rows**, including old name-derived owners. No client route changes this flag. Those bookings still reserve active slots, but cannot be read/mutated through the private API until an administrator independently verifies ownership and reassigns/enables the row. Do not bulk-enable or infer owners from names/UUIDs. This task supplies no administrative reassignment endpoint. New ORM-created bookings are enabled for upstream-asserted ownership; that is not proof of authentication. Do not downgrade to the old unsafe application contract without a separate review.

## Reproduce in isolation (repository root)

Python >=3.12; recorded run: Python 3.14.4, pytest 9.2.0, asyncpg 0.32.0, coverage 7.17.2.
The repository compose file is `backend/compose.test.yaml` with `booking:booking`, database `booking_test`, port 55432. Inspecting it is safe:

```bash
docker compose -f backend/compose.test.yaml config
```

For this correction, use a **new** container with no shared volume. The actual isolated setup used:

```bash
docker run -d --name vt116-final-postgres --label purpose=vt116-final-isolated \
  -e POSTGRES_DB=vt116_final_test -e POSTGRES_USER=booking -e POSTGRES_PASSWORD=booking \
  -p 127.0.0.1:55433:5432 --tmpfs /var/lib/postgresql postgres:18-alpine
docker exec vt116-final-postgres pg_isready -U booking -d vt116_final_test
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[dev]'
export TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55433/vt116_final_test
export BOOKING_DATABASE_URL="$TEST_DATABASE_URL"
export PYTHONPATH=.:backend
```

Wait until pg_isready succeeds. A container already named `vt116-final-postgres` must be inspected before reuse; do not delete an unfamiliar container. The following migration drill requires a fresh database and must run **before pytest/load**, which create/drop/truncate test tables:

```bash
backend/.venv/bin/python scripts/verify_vt116_migration.py
backend/.venv/bin/python scripts/capture_vt116_evidence.py /tmp/vt116-targeted.log \
  backend/.venv/bin/pytest backend/tests/unit/test_soft_delete_restore.py \
  backend/tests/integration/test_soft_delete_restore_api.py \
  backend/tests/integration/test_vt116_security_transitions.py -v -p no:cacheprovider
backend/.venv/bin/python scripts/capture_vt116_evidence.py /tmp/vt116-full.log \
  backend/.venv/bin/pytest backend/tests -v -p no:cacheprovider
```

Recorded final code results: targeted 33 PASS; full **117 PASS / 0 FAIL / 0 SKIP**, one upstream Starlette deprecation warning. Historical GREEN has only 17 tests; it is preserved, not relabeled as a 96-test run.

## Coverage and flaky checks

```bash
COVERAGE_CORE=sysmon backend/.venv/bin/python -m coverage run --branch \
  --source=backend/app -m pytest backend/tests -q -p no:cacheprovider
backend/.venv/bin/python -m coverage report -m
backend/.venv/bin/python -m coverage json -o /tmp/vt116-coverage.json
backend/.venv/bin/python scripts/verify_vt116_flaky.py
backend/.venv/bin/ruff check .
backend/.venv/bin/ruff format --check .
```

sysmon applies to the recorded Python 3.14 environment; other supported Python versions may use their default coverage core. The old exit-139 root cause is NOT VERIFIED: the final sysmon run completed successfully, so no integration-coverage estimate is needed. Full-app statement coverage: 808/859 (94.06%); branch coverage: 166/200 (83.00%). These are separate from coverage.py's combined 91.97% summary. Risk coverage and open limitations are in the strategy/traceability.

## One deliberate mutation (temporary branch only)

The actual guarded rule in `backend/app/services/booking.py::BookingService.soft_delete` is `if owner != caller_id:`. Change **only that occurrence** to `if owner == caller_id:` after its historical-owner guard, on a temporary branch/worktree. Never mutate the submitted branch.

```bash
git worktree add -b vt116-mutation-reproduce /tmp/vt116-mutation HEAD
# Edit only the soft_delete owner comparison in that worktree, review git diff, commit there.
# From that worktree, use the original absolute venv Python path to run:
# python -m pytest backend/tests/unit/test_soft_delete_restore.py \
#   backend/tests/integration/test_soft_delete_restore_api.py \
#   backend/tests/integration/test_vt116_security_transitions.py -q -p no:cacheprovider
```

Recorded temporary mutation SHA `1b707ea`: **12 FAIL / 21 PASS**, therefore that one mutation is KILLED. This is not a general mutation coverage percentage. The worktree was removed and the mutation was not merged. Original historical mutation log remains unchanged.

## Performance (same workload, paired evidence)

```bash
backend/.venv/bin/python scripts/loadtest_vt116.py --output-dir /tmp/vt116-load
# Use the exact JSON path printed by the command:
backend/.venv/bin/python scripts/verify_vt116_performance_evidence.py \
  docs/bt3-vt116/evidence/final/performance-20261109T063500Z-038fb4c8.json
```

Recorded run `20261109T063500Z-038fb4c8`: 200 measured create/delete/restore lifecycles, 600 requests, cap 40, measured peak lifecycle/HTTP in-flight 40/40, 0 errors, p95 **420.11 ms** <=1500 ms. Warmup: 5 lifecycles, excluded from counters/duration. Runtime 1.8398 s; throughput 108.71 lifecycle/s. Raw samples and matching metrics are in the paired JSON/log. `ASGITransport` runs HTTP in-process against real PostgreSQL; no network HTTP overhead, IdP/gateway or production capacity claim is made. Semaphore caps concurrency; it does not guarantee 40 continuously active requests.

Earlier JSON/log were overwritten at different times and lack a common run ID (log p95 482.70 ms versus JSON 602.2 ms). Their precise historical execution lineage cannot be reconstructed. They are excluded from the final result and recoverable from Git commit `58ad4e4`; stale local duplicates were removed.

## Documents and artifacts

- `final-correction-plan.md`: assumptions/plan before patch.
- `test-strategy.md`: five ACs, state table and risk-based cases.
- `traceability-and-ai-log.md`: exact functions/files/commits/results and AI usage.
- `evidence/final/`: new immutable run outputs, raw coverage and paired performance artifacts.
- `report/BT3_23001827_VT-116.tex` and `.pdf`: final report; root workspace copies have the same content.
- `final-acceptance.md`: final checks, limitations, GitHub status.

For PDF rebuild, use the installed Docker image `blang/latex:ubuntu` and XeLaTeX as documented in the PDF QA evidence. Main content is at most 8 pages; appendix contains full traceability and AI log. The reflection and commitment are for the student's review/confirmation, not signed by AI.
