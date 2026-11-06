"""Automated rollback trigger via GitHub repository_dispatch (TASK-007 / C187).

Allows alert webhooks (Alertmanager/Discord), SRE scripts, or automated monitoring
probes to dispatch an emergency rollback event to GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

DEFAULT_EVENT_TYPE = "alert-rollback"


def build_dispatch_payload(
    alert_name: str = "BookingHighHttpErrorRate",
    reason: str = "Automated rollback triggered by alert webhook",
    target_manifest: str = "",
    severity: str = "critical",
    source: str = "alertmanager",
    triggered_by: str = "automation",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the repository_dispatch request body payload."""
    ts = (now or datetime.now(UTC)).isoformat()
    return {
        "event_type": DEFAULT_EVENT_TYPE,
        "client_payload": {
            "alert_name": alert_name,
            "reason": reason,
            "target_manifest": target_manifest,
            "severity": severity,
            "source": source,
            "triggered_by": triggered_by,
            "triggered_at": ts,
        },
    }


def send_rollback_dispatch(
    repo: str,
    token: str,
    payload: dict[str, Any],
    dry_run: bool = False,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Send repository_dispatch event to GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/dispatches"
    body = json.dumps(payload).encode("utf-8")

    if dry_run:
        print(f"[DRY-RUN] Would send POST {url} with headers:")
        print("  Accept: application/vnd.github.v3+json")
        print("  Authorization: Bearer <TOKEN>")
        print(f"Payload:\n{json.dumps(payload, indent=2)}")
        return {"status": "dry-run", "url": url, "payload": payload}

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "booking-automated-rollback-trigger/1.0",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # GitHub returns 204 No Content for successful repository_dispatch
            if resp.status not in (200, 204):
                raise RuntimeError(f"GitHub API returned HTTP {resp.status}")
            return {
                "status": "success",
                "status_code": resp.status,
                "url": url,
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API dispatch failed (HTTP {exc.code}): {err_msg}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to dispatch rollback event to {url}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trigger automated rollback via GitHub repository_dispatch."
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPOSITORY", ""),
        help="Target GitHub repository (owner/repo). Defaults to GITHUB_REPOSITORY env var.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub personal access token or actions token. Defaults to GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--alert-name",
        default="BookingHighHttpErrorRate",
        help="Name of firing alert causing the rollback.",
    )
    parser.add_argument(
        "--reason",
        default="Automated rollback triggered by alert webhook",
        help="Descriptive reason for triggering rollback.",
    )
    parser.add_argument(
        "--target-manifest",
        default="",
        help="Optional target manifest path on demo host (empty = previous-manifest.json).",
    )
    parser.add_argument(
        "--severity",
        default="critical",
        choices=["critical", "warning", "info"],
        help="Incident severity level.",
    )
    parser.add_argument(
        "--source",
        default="alertmanager",
        help="Source of trigger (alertmanager, script, manual).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print dispatch request without sending HTTP request.",
    )
    args = parser.parse_args()

    if not args.dry_run:
        if not args.repo:
            print("[FATAL] --repo or GITHUB_REPOSITORY is required.", file=sys.stderr)
            sys.exit(2)
        if not args.token:
            print("[FATAL] --token or GITHUB_TOKEN is required.", file=sys.stderr)
            sys.exit(2)

    payload = build_dispatch_payload(
        alert_name=args.alert_name,
        reason=args.reason,
        target_manifest=args.target_manifest,
        severity=args.severity,
        source=args.source,
    )

    try:
        res = send_rollback_dispatch(
            repo=args.repo or "owner/repo",
            token=args.token,
            payload=payload,
            dry_run=args.dry_run,
        )
        print(f"[SUCCESS] Rollback dispatch triggered: {res['status']}")
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
