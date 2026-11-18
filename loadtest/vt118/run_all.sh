#!/usr/bin/env bash
# Run the VT-118 load matrix: one fresh API process per notifier behaviour, 60 concurrent workers.
#
#   LABEL=after loadtest/vt118/run_all.sh            # after the patch (all scenarios)
#   LABEL=baseline SCENARIOS="default:valid" loadtest/vt118/run_all.sh
#   BACKEND_DIR=../baseline-worktree/backend LABEL=baseline-r2 loadtest/vt118/run_all.sh
#
# BACKEND_DIR selects which backend code the API process runs (default: ./backend), so the same
# harness can measure the baseline commit or an experimental variant from a git worktree.
#
# Requirements: PostgreSQL reachable at $PG_URL with a database whose name ends in _test,
# Python env with backend[dev] installed. Run from the repository root.
set -euo pipefail

LABEL="${LABEL:-after}"
PORT="${PORT:-8018}"
PG_URL="${PG_URL:-postgresql://booking:booking@127.0.0.1:55432/booking_load_test}"
OUT_DIR="${OUT_DIR:-docs/vt118/evidence/load}"
CONCURRENCY="${CONCURRENCY:-60}"
REQUESTS_PER_WORKER="${REQUESTS_PER_WORKER:-10}"
SCENARIOS="${SCENARIOS:-default:valid ok:valid fail:valid hang:valid ok:valid-100 ok:oversized-1mb}"
BACKEND_DIR="${BACKEND_DIR:-backend}"

export BOOKING_DATABASE_URL="${PG_URL/postgresql:/postgresql+asyncpg:}"
export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$OUT_DIR"

(cd backend && alembic upgrade head >/dev/null 2>&1)

for item in $SCENARIOS; do
  notifier="${item%%:*}"
  payload="${item##*:}"
  name="${LABEL}-${notifier}-${payload}"
  python loadtest/vt118/serve.py --notifier "$notifier" --port "$PORT" \
    >"$OUT_DIR/${name}.server.log" 2>&1 &
  server_pid=$!
  for _ in $(seq 1 50); do
    curl -fsS "http://127.0.0.1:${PORT}/health/live" >/dev/null 2>&1 && break
    sleep 0.2
  done
  python loadtest/vt118/load_notifications.py \
    --scenario "$name" --payload "$payload" \
    --base-url "http://127.0.0.1:${PORT}" --db-url "$PG_URL" \
    --concurrency "$CONCURRENCY" --requests-per-worker "$REQUESTS_PER_WORKER" \
    --output "$OUT_DIR/${name}.json" >/dev/null
  kill "$server_pid" && wait "$server_pid" 2>/dev/null || true
  python - "$OUT_DIR/${name}.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
lat = r["latency_seconds"]
print(f'{r["scenario"]:<32} n={r["total_requests"]:<4} peak={r["peak_in_flight"]:<3} '
      f'p50={lat["p50"]:.3f}s p95={lat["p95"]:.3f}s p99={lat["p99"]:.3f}s max={lat["max"]:.3f}s '
      f'status={r["status_counts"]} notif={r["notification_status_counts"]} '
      f'rows_ok={r["rows_match_201"]} p95<=2.0s={r["p95_within_target"]} no5xx={r["no_5xx"]}')
PY
done
