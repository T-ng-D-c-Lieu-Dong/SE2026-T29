# VT-116 Final Correction Implementation Plan

**Goal:** Correct the existing VT-116 slice, preserve historical evidence, and produce a reviewable report.
**Spec:** User's FINAL CORRECTION instructions, 2026-11-09.
**Architecture:** Keep FastAPI/SQLAlchemy/PostgreSQL. Require caller identity on all private booking routes. Treat X-User-Id as a trusted-upstream assertion, not authentication; direct spoofing remains demonstrable. Quarantine reserved legacy owners independently of UUID secrecy. Public routes expose slot availability and operational health only.
**Tech stack:** Python, pytest, httpx ASGITransport, PostgreSQL 18, coverage.py, XeLaTeX.

## Assumptions and decisions before code
- No IdP exists. Rejected: a nonempty header authenticates a person.
- Rejected: legacy_<UUID> is secret or confers access rights. Reserved identities cannot be asserted through booking API; legacy rows remain inaccessible pending verified administrative reassignment.
- Existing anonymous create/read/cancel contracts must change. Preserve their business behavior in regression tests by explicitly supplying caller identity; add separate negative tests for missing identity.
- Use a new PostgreSQL container on loopback port 55433, with no persistent/shared volume. Never connect test cleanup to port 55432 or a shared database.
- Preserve RED/GREEN historical files. New runs carry command, environment, tested SHA and run ID. Documentation commits may follow the tested code SHA.
- Keep original 200 create/delete/restore lifecycles, concurrency cap 40. Measure peak lifecycle and request in-flight separately; exclude warmup from duration.
- Report reflection is an AI-assisted draft for student review; do not attest to personal experience or sign the academic commitment.

## Review focus
Missing/blank/oversized identity; name collisions; reserved legacy headers; client owner payload disagreement; direct forged header; cancelled/past transitions; failed workload incorrectly marked successful; shared-state/order and clock dependence.

## Execution tasks (native, as explicitly requested)
1. [ ] Add `backend/tests/integration/test_vt116_security_transitions.py`: missing identity, cross-user list/detail, name collisions, legacy read/write, forged header characterization, TC-11, cancelled delete/restore and deleted cancel. Run RED against unmodified code and save `evidence/final/01-security-red.log`.
2. [ ] Patch `backend/app/api/appointments.py`, ownership rules in service/repository, and adapt existing positive regression fixtures to the explicit caller contract. Run targeted GREEN, review diff, commit security/tests separately.
3. [ ] Fix `scripts/loadtest_vt116.py`: one run ID, immutable paired JSON/log output, peaks, complete metrics, failures affect verdict. Targeted tests for workload failure verdict/percentiles. Run independent load experiment.
4. [ ] Run final full pytest suite, line/branch coverage, temporary-branch owner-rule mutation and deterministic repeated/reversed-order runs against isolated database. Save unedited outputs and exact tested commits.
5. [ ] Replace outdated README/strategy/traceability with exact runnable commands and five ACs. Preserve audit/plan as historical with notices. Add AI log and explicit limits. Commit evidence/docs separately.
6. [ ] Correct root LaTeX, render all pages with XeLaTeX, verify no overfull boxes/cut text and <=8 main pages; add report source/PDF to deliverable branch as explicitly requested despite prior ignore defaults. Back up current report first.
7. [ ] Check remote, push personal branch without force if permitted; verify remote SHA. Update final acceptance evidence and report with verified URL or BLOCKED. Record final commit and status.

No merge, history rewrite, broader backend refactor, invented measurements or student sign-off.
