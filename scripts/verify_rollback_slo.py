"""Verify rollback duration against 5-minute (300-second) SLO target (TASK-007 / E12).

Measures and confirms whether the most recent rollback operation succeeded within
the mandated 5-minute recovery threshold, providing deterministic reporting for CI/CD gates.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.deploy_history import DeploymentHistory
from scripts.drill_timeline import DrillTimeline, default_timeline_path

DEFAULT_ROLLBACK_SLO_SECONDS: float = 300.0


@dataclass
class RollbackSloResult:
    operation: str
    release: str
    commit_sha: str
    duration_seconds: float
    target_seconds: float
    slo_met: bool
    margin_seconds: float
    started_at: str
    ended_at: str
    source: str  # "history" or "timeline"
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_text(self) -> str:
        status_text = "PASS" if self.slo_met else "FAIL"
        lines = [
            "=" * 60,
            f"Rollback SLO Verification: [{status_text}]",
            f"  Target SLO Threshold : <= {self.target_seconds:.2f}s (5 minutes)",
            f"  Actual Duration      : {self.duration_seconds:.2f}s",
            f"  Margin               : {self.margin_seconds:+.2f}s",
            f"  Restored Release     : {self.release} ({self.commit_sha[:8]})",
            f"  Started At (UTC)     : {self.started_at}",
            f"  Ended At (UTC)       : {self.ended_at}",
            f"  Data Source          : {self.source}",
            "=" * 60,
        ]
        return "\n".join(lines)


def evaluate_rollback_slo(
    state_dir: Path | str | None = None,
    timeline_file: Path | str | None = None,
    target_seconds: float = DEFAULT_ROLLBACK_SLO_SECONDS,
) -> RollbackSloResult:
    """Evaluate the most recent rollback duration against the SLO threshold.

    Checks DeploymentHistory first. If no rollback entry is recorded in history,
    falls back to DrillTimeline.
    """
    resolved_state_dir = Path(state_dir or os.getenv("BOOKING_STATE_DIR", "deploy")).resolve()
    history = DeploymentHistory(state_dir=resolved_state_dir)
    entries = history.load_entries()

    # Find the most recent rollback operation in history
    rollback_entries = [e for e in entries if e.get("operation") == "rollback"]
    if rollback_entries:
        last_op = rollback_entries[-1]
        duration = float(last_op.get("duration_seconds", 0.0))
        slo_met = duration <= target_seconds
        margin = round(target_seconds - duration, 2)
        return RollbackSloResult(
            operation="rollback",
            release=str(last_op.get("release", "unknown")),
            commit_sha=str(last_op.get("commit_sha", "unknown")),
            duration_seconds=duration,
            target_seconds=target_seconds,
            slo_met=slo_met,
            margin_seconds=margin,
            started_at=str(last_op.get("started_at", "")),
            ended_at=str(last_op.get("ended_at", "")),
            source=f"history:{history.history_file}",
            details=last_op,
        )

    # Fallback to drill timeline
    tl_path = Path(timeline_file).resolve() if timeline_file else default_timeline_path()
    if tl_path.is_file():
        timeline = DrillTimeline.load(tl_path)
        tl_duration = timeline.rollback_duration_seconds()
        if tl_duration is not None:
            rb_start = timeline.get_event("rollback_start")
            rb_comp = timeline.get_event("rollback_complete")
            started_at = rb_start.timestamp if rb_start else ""
            ended_at = rb_comp.timestamp if rb_comp else ""
            slo_met = tl_duration <= target_seconds
            margin = round(target_seconds - tl_duration, 2)
            return RollbackSloResult(
                operation="rollback",
                release=timeline.drill_id,
                commit_sha="timeline",
                duration_seconds=tl_duration,
                target_seconds=target_seconds,
                slo_met=slo_met,
                margin_seconds=margin,
                started_at=started_at,
                ended_at=ended_at,
                source=f"timeline:{tl_path}",
                details={"drill_id": timeline.drill_id, "events_count": len(timeline.events)},
            )

    raise ValueError(
        f"No rollback operations found in history at {history.history_file} "
        f"or timeline at {tl_path}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify rollback duration against 5-minute SLO target."
    )
    default_state = os.getenv("BOOKING_STATE_DIR", "deploy")
    parser.add_argument(
        "--state-dir",
        default=default_state,
        help="Directory where deploy/rollback history is stored (default: BOOKING_STATE_DIR)",
    )
    parser.add_argument(
        "--timeline-file",
        help="Optional path to drill-timeline.json if checking from timeline",
    )
    parser.add_argument(
        "--target-seconds",
        type=float,
        default=DEFAULT_ROLLBACK_SLO_SECONDS,
        help="SLO target duration in seconds (default: 300.0s = 5 minutes)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON object",
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="Exit with code 1 if duration exceeds target_seconds",
    )
    args = parser.parse_args()

    try:
        result = evaluate_rollback_slo(
            state_dir=args.state_dir,
            timeline_file=args.timeline_file,
            target_seconds=args.target_seconds,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary_text())

        if args.fail_on_violation and not result.slo_met:
            msg = (
                f"[ERROR] Rollback duration ({result.duration_seconds:.2f}s) "
                f"exceeded SLO ({args.target_seconds:.2f}s)!"
            )
            print(msg, file=sys.stderr)
            sys.exit(1)

    except Exception as exc:
        print(f"[FATAL] Could not evaluate rollback SLO: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
