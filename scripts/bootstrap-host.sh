#!/usr/bin/env bash
# Prepare an Ubuntu demo host for the self-hosted deploy runner (TASK-004).
# Installs Docker Engine + Compose v2, Python 3 and GitHub CLI, then creates the
# persistent state directory used by scripts/deploy.py and scripts/rollback.py.
# Safe to run more than once.
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-${SUDO_USER:-}}"
STATE_DIR="${BOOKING_STATE_DIR:-/opt/booking/state}"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi

if [[ -z "$RUNNER_USER" || "$RUNNER_USER" == "root" ]]; then
    echo "Set RUNNER_USER to the non-root user that will run the GitHub runner." >&2
    exit 1
fi

if ! id "$RUNNER_USER" &>/dev/null; then
    echo "User '$RUNNER_USER' does not exist." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q

if docker compose version &>/dev/null; then
    echo "[INFO] Docker Compose already installed: $(docker compose version --short)"
else
    apt-get install -y -q docker.io docker-compose-v2
fi
apt-get install -y -q python3 python3-venv git curl gh

systemctl enable --now docker
usermod -aG docker "$RUNNER_USER"

# State lives outside the runner workspace so manifests survive between jobs.
install -d -m 0750 -o "$RUNNER_USER" -g "$RUNNER_USER" "$STATE_DIR"

echo "[OK] Host ready."
echo "     Docker:    $(docker --version)"
echo "     Compose:   $(docker compose version --short)"
echo "     State dir: $STATE_DIR (owner: $RUNNER_USER)"
echo "Log out and back in so '$RUNNER_USER' picks up the docker group."
