"""Drill timeline recorder for incident simulation and recovery verification (E12/E14)."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STANDARD_EVENTS = (
    "drill_start",
    "alert_fired",
    "investigation_start",
    "rollback_start",
    "rollback_complete",
    "service_restored",
)


@dataclass
class TimelineEvent:
    event: str
    timestamp: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dt(self) -> datetime:
        return datetime.fromisoformat(self.timestamp)


@dataclass
class DrillTimeline:
    drill_id: str
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    events: list[TimelineEvent] = field(default_factory=list)

    def record_event(
        self,
        event: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> TimelineEvent:
        ts = (now or datetime.now(UTC)).isoformat()
        ev = TimelineEvent(
            event=event,
            timestamp=ts,
            description=description,
            metadata=metadata or {},
        )
        self.events.append(ev)
        return ev

    def get_event(self, event_name: str) -> TimelineEvent | None:
        for ev in reversed(self.events):
            if ev.event == event_name:
                return ev
        return None

    def rollback_duration_seconds(self) -> float | None:
        start = self.get_event("rollback_start")
        end = self.get_event("rollback_complete")
        if start and end:
            diff = (end.dt - start.dt).total_seconds()
            return max(0.0, diff)
        return None

    def mttr_seconds(self) -> float | None:
        start = self.get_event("drill_start") or self.get_event("alert_fired")
        restored = self.get_event("service_restored") or self.get_event("rollback_complete")
        if start and restored:
            diff = (restored.dt - start.dt).total_seconds()
            return max(0.0, diff)
        return None

    def meets_rollback_target(self, target_seconds: float = 300.0) -> bool:
        """Returns True if rollback completed within target (default: 5 minutes / 300s)."""
        duration = self.rollback_duration_seconds()
        if duration is None:
            return False
        return duration <= target_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "created_at": self.created_at,
            "events": [asdict(ev) for ev in self.events],
            "metrics": {
                "rollback_duration_seconds": self.rollback_duration_seconds(),
                "mttr_seconds": self.mttr_seconds(),
                "meets_rollback_target": self.meets_rollback_target(),
            },
        }

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> DrillTimeline:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Timeline file not found: {path}")
        data = json.loads(p.read_text(encoding="utf-8"))
        events = [TimelineEvent(**item) for item in data.get("events", [])]
        return cls(
            drill_id=data.get("drill_id", "unspecified"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            events=events,
        )

    def to_markdown_table(self) -> str:
        lines = [
            "| Event | Timestamp (UTC) | Relative | Description |",
            "| :--- | :--- | :--- | :--- |",
        ]
        start_dt = self.events[0].dt if self.events else None
        for ev in self.events:
            if start_dt:
                rel = f"+{int((ev.dt - start_dt).total_seconds())}s"
            else:
                rel = "+0s"
            lines.append(f"| `{ev.event}` | {ev.timestamp} | {rel} | {ev.description} |")
        return "\n".join(lines)


def default_timeline_path() -> Path:
    env_dir = os.environ.get("BOOKING_STATE_DIR")
    if env_dir:
        return Path(env_dir) / "drill-timeline.json"

    # Support backwards compatibility with legacy deploy/state path, default to deploy
    legacy_path = Path("deploy/state/drill-timeline.json")
    if legacy_path.is_file():
        return legacy_path
    return Path("deploy/drill-timeline.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and report drill incident timeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_p = subparsers.add_parser("record", help="Record a timeline event")
    record_p.add_argument("--event", required=True, help=f"Event name, e.g. {STANDARD_EVENTS}")
    record_p.add_argument("--description", default="", help="Event description / note")
    record_p.add_argument("--drill-id", default="drill-demo", help="Identifier for the drill")
    record_p.add_argument("--file", help="Path to timeline JSON file")

    report_p = subparsers.add_parser("report", help="Display summary and markdown table")
    report_p.add_argument("--file", help="Path to timeline JSON file")

    clear_p = subparsers.add_parser("clear", help="Clear or reset timeline")
    clear_p.add_argument("--file", help="Path to timeline JSON file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    timeline_file = Path(args.file) if getattr(args, "file", None) else default_timeline_path()

    if args.command == "record":
        if timeline_file.is_file():
            timeline = DrillTimeline.load(timeline_file)
        else:
            timeline = DrillTimeline(drill_id=args.drill_id)
        ev = timeline.record_event(args.event, args.description)
        timeline.save(timeline_file)
        print(f"Recorded [{ev.event}] at {ev.timestamp} to {timeline_file}")

    elif args.command == "report":
        if not timeline_file.is_file():
            print(f"No timeline found at: {timeline_file}")
            return
        timeline = DrillTimeline.load(timeline_file)
        print(f"Drill ID: {timeline.drill_id} (Events: {len(timeline.events)})")
        rb = timeline.rollback_duration_seconds()
        mttr = timeline.mttr_seconds()
        print(f"Rollback duration: {rb:.2f}s" if rb is not None else "Rollback duration: N/A")
        print(f"MTTR: {mttr:.2f}s" if mttr is not None else "MTTR: N/A")
        print(f"Rollback target (<300s): {'PASS' if timeline.meets_rollback_target() else 'FAIL'}")
        print("\nMarkdown Table:\n")
        print(timeline.to_markdown_table())

    elif args.command == "clear":
        if timeline_file.is_file():
            timeline_file.unlink()
            print(f"Removed timeline: {timeline_file}")
        else:
            print("Timeline file does not exist.")


if __name__ == "__main__":
    main()
