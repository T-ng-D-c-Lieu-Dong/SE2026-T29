"""Unified SRE Operational CLI (TASK-005 / TASK-007 Hardening).

Centralizes all SRE and Reliability operations into a single developer-friendly CLI:
- sre status: Displays active manifest, container health, and deploy lock status.
- sre health: Performs instant readiness probe and smoke test verification.
- sre rollback: Triggers guarded rollback to a target release manifest.
- sre snapshot: Manages database and booking integrity snapshots.
- sre budget: Calculates rolling SLO error budget consumption and burn rate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_status(args: argparse.Namespace) -> int:
    from scripts.deploy_lock import DeploymentLock
    from scripts.release_manifest import ReleaseManifest

    state_dir = Path(args.state_dir)
    curr_manifest_file = state_dir / "current-manifest.json"
    print("=" * 60)
    print("SE2026-T29 Operational Status")
    print("=" * 60)

    if curr_manifest_file.is_file():
        try:
            m = ReleaseManifest.load(curr_manifest_file)
            print(f"Active Release:     {m.release}")
            print(f"Commit SHA:         {m.commit_sha}")
            print(f"Migration Revision: {m.migration_revision}")
            print(f"Manifest Integrity: {m.compute_checksum()[:16]}...")
        except Exception as exc:
            print(f"Active Release:     CORRUPTED ({exc})")
    else:
        print("Active Release:     None (current-manifest.json absent)")

    lock = DeploymentLock(lock_dir=state_dir / ".deploy.lock")
    lock_info = lock._inspect_existing_lock()
    if lock_info:
        op = lock_info.get("operation")
        at = lock_info.get("acquired_at")
        print(f"Deployment Lock:    LOCKED (by {op} since {at})")
    else:
        print("Deployment Lock:    UNLOCKED (Ready)")

    print("=" * 60)
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    from scripts.smoke_test import SmokeTestRunner

    runner = SmokeTestRunner(base_url=args.base_url)
    results = runner.run_all()
    all_ok = True
    print("=" * 60)
    print(f"Running System Health & Business Smoke Tests ({args.base_url})")
    print("=" * 60)
    for r in results:
        status = "PASS" if r.success else "FAIL"
        print(f"[{status}] ({r.duration_seconds:.2f}s) {r.step}: {r.message}")
        if not r.success:
            all_ok = False
    return 0 if all_ok else 1


def cmd_rollback(args: argparse.Namespace) -> int:
    from scripts.rollback import Rollbacker

    rollbacker = Rollbacker(
        target_manifest=args.target_manifest,
        state_dir=args.state_dir,
        base_url=args.base_url,
        dry_run=args.dry_run,
        skip_container_ops=args.skip_container_ops,
        enforce_guard=not args.no_guard,
    )
    rollbacker.run()
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    from scripts.calculate_error_budget import ErrorBudgetCalculator

    calc = ErrorBudgetCalculator(slo_target=args.slo)
    res = calc.calculate(args.total, args.errors, window_hours=args.window_hours)
    print("=" * 60)
    print(f"SLO Target: {res.slo_target * 100:.1f}%")
    print(f"Observed Error Rate: {res.observed_error_rate * 100:.2f}%")
    print(f"Burn Rate: {res.burn_rate}x (Budget consumed: {res.consumed_budget_percent}%)")
    print(f"Status: [{res.status}]")
    print("=" * 60)
    return 1 if res.is_violating else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sre",
        description="Unified SRE Operational CLI for SE2026-T29 Booking Platform",
    )
    parser.add_argument("--state-dir", default="deploy", help="State directory (default: deploy)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Booking API Base URL")

    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show system release and lock status")

    # health
    sub.add_parser("health", help="Run health and smoke tests")

    # rollback
    rb = sub.add_parser("rollback", help="Execute guarded rollback")
    rb.add_argument("--target-manifest", default="deploy/previous-manifest.json")
    rb.add_argument("--dry-run", action="store_true")
    rb.add_argument("--skip-container-ops", action="store_true")
    rb.add_argument("--no-guard", action="store_true")

    # budget
    bg = sub.add_parser("budget", help="Calculate SLO error budget burn rate")
    bg.add_argument("--total", type=int, required=True)
    bg.add_argument("--errors", type=int, required=True)
    bg.add_argument("--window-hours", type=float, default=1.0)
    bg.add_argument("--slo", type=float, default=0.99)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "status": cmd_status,
        "health": cmd_health,
        "rollback": cmd_rollback,
        "budget": cmd_budget,
    }
    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))


if __name__ == "__main__":
    main()
