#!/usr/bin/env bash
# VT-118 mutation experiment: "change the mapping of a response field".
#
# Applies each mutant patch to a clean working tree, runs the test set, reports KILLED/SURVIVED
# with the tests that caught it, then restores backend/app. Mutants are never committed to the
# submission branch (see docs/vt118/README.md).
#
#   TEST_DATABASE_URL=postgresql+asyncpg://booking:booking@127.0.0.1:55432/booking_test \
#     docs/vt118/mutations/run_mutations.sh [patch ...]
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

TESTS="${TESTS:-backend/tests/unit/test_booking_notifications.py \
backend/tests/integration/test_appointment_notifications.py \
backend/tests/integration/test_appointments_api.py \
backend/tests/integration/test_release_e08_e12_e14.py}"

if ! git diff --quiet -- backend/app; then
  echo "backend/app has uncommitted changes; refusing to run" >&2
  exit 2
fi
trap 'git checkout -q -- backend/app' EXIT

patches=("$@")
[ ${#patches[@]} -eq 0 ] && patches=(docs/vt118/mutations/M*.patch)

echo "# baseline (no mutant): $(python -m pytest -q -p no:cacheprovider --tb=no $TESTS 2>&1 | tail -1)"
for patch in "${patches[@]}"; do
  name="$(basename "$patch" .patch)"
  if ! git apply "$patch"; then
    echo "$name: PATCH DOES NOT APPLY"
    continue
  fi
  output="$(python -m pytest -q -p no:cacheprovider --tb=no -rf $TESTS 2>&1)"
  failed="$(grep -c '^FAILED' <<<"$output")"
  if [ "$failed" -gt 0 ]; then
    echo "$name: KILLED by $failed test(s)"
    grep '^FAILED' <<<"$output" | sed -E 's/^FAILED ([^ ]+).*/    - \1/'
  else
    echo "$name: SURVIVED ($(tail -1 <<<"$output"))"
  fi
  git checkout -q -- backend/app
done
