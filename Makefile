.PHONY: help loadtest loadtest-e15 loadtest-conflict smoke-test deploy rollback drill-start drill-alert drill-rollback drill-complete drill-report snapshot-bookings verify-integrity test

BASE_URL ?= http://localhost:8000
DURATION ?= 30s
TARGET_RPS ?= 10
SNAPSHOT_FILE ?= /tmp/booking-baseline.json

help:
	@echo "SE2026-T29 Operational Makefile"
	@echo ""
	@echo "Load Testing (k6):"
	@echo "  make loadtest           Run quick k6 load test (default: 30s)"
	@echo "  make loadtest-e15       Run full 10-minute E15 load test (10m @ 10 RPS)"
	@echo "  make loadtest-conflict  Run load test with deliberate 409 conflict scenario"
	@echo ""
	@echo "Incident Drill & Rollback:"
	@echo "  make drill-start        Record drill start milestone"
	@echo "  make drill-alert        Record alert fired milestone"
	@echo "  make drill-rollback     Record rollback triggered milestone"
	@echo "  make drill-complete     Record rollback finished milestone"
	@echo "  make drill-report       Generate and display drill timeline report"
	@echo "  make snapshot-bookings  Capture bookings snapshot before drill"
	@echo "  make verify-integrity   Verify bookings integrity after rollback"
	@echo "  make rollback           Execute rollback to previous release manifest"
	@echo "  make smoke-test         Run smoke test verification"
	@echo ""
	@echo "Testing & CI:"
	@echo "  make test               Run unit tests (Python & Node.js)"

loadtest:
	k6 run -e BASE_URL=$(BASE_URL) -e DURATION=$(DURATION) -e TARGET_RPS=$(TARGET_RPS) loadtest/booking.js

loadtest-e15:
	k6 run -e BASE_URL=$(BASE_URL) -e DURATION=10m -e TARGET_RPS=10 loadtest/booking.js

loadtest-conflict:
	k6 run -e BASE_URL=$(BASE_URL) -e DURATION=$(DURATION) -e TARGET_RPS=$(TARGET_RPS) -e CONFLICT_SCENARIO=true loadtest/booking.js

snapshot-bookings:
	python3 -m scripts.booking_integrity snapshot --output $(SNAPSHOT_FILE) --base-url $(BASE_URL)

verify-integrity:
	python3 -m scripts.booking_integrity verify --baseline $(SNAPSHOT_FILE) --base-url $(BASE_URL)

drill-start:
	python3 -m scripts.drill_timeline record --event drill_start --description "Deploy drill release"

drill-alert:
	python3 -m scripts.drill_timeline record --event alert_fired --description "Alert fired on Alertmanager"

drill-rollback:
	python3 -m scripts.drill_timeline record --event rollback_start --description "Trigger rollback deployment"

drill-complete:
	python3 -m scripts.drill_timeline record --event rollback_complete --description "Rollback smoke test passed"

drill-report:
	python3 -m scripts.drill_timeline report

rollback:
	python3 -m scripts.rollback

smoke-test:
	python3 -m scripts.smoke_test

test:
	node --experimental-vm-modules --test loadtest/tests/booking.test.mjs
	PYTHONPATH=. pytest backend/tests/unit/test_drill_timeline.py backend/tests/unit/test_booking_integrity.py
