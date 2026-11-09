#!/usr/bin/env bash
# Rollback script for Booking API with mutex lock, health verification, and data preservation.
set -euo pipefail

TARGET_MANIFEST="${1:-${BOOKING_STATE_DIR:-deploy}/previous-manifest.json}"

PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &>/dev/null; then
    PYTHON_CMD="python"
fi

exec "$PYTHON_CMD" -m scripts.rollback --target-manifest "$TARGET_MANIFEST" "$@"
