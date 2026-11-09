"""Deployment and rollback history recorder.

Implements TASK-005 / TASK-007 requirements:
- "Đo thời gian deploy/rollback, ghi vào history file"
- Records start and end timestamps, duration, status, release, commit SHA, and SLO metrics.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any


@dataclass
class HistoryEntry:
    operation: str  # "deploy" or "rollback"
    release: str
    commit_sha: str
    status: str  # "success" or "failed"
    started_at: str  # ISO 8601 UTC
    ended_at: str  # ISO 8601 UTC
    duration_seconds: float
    error: str | None = None
    slo_met: bool | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.error is None:
            data.pop("error", None)
        if self.slo_met is None:
            data.pop("slo_met", None)
        if not self.details:
            data.pop("details", None)
        return data


class DeploymentHistory:
    """Manages reading and appending deploy and rollback history records."""

    def __init__(
        self,
        state_dir: Path | str = "deploy",
        filename: str = "history.json",
    ) -> None:
        self.state_dir = Path(state_dir).resolve()
        self.history_file = self.state_dir / filename

    def load_entries(self) -> list[dict[str, Any]]:
        """Load history entries from the history file if it exists."""
        if not self.history_file.exists():
            return []
        try:
            content = self.history_file.read_text(encoding="utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
            return []
        except (OSError, json.JSONDecodeError):
            return []

    def append_entry(self, entry: HistoryEntry) -> None:
        """Atomically append a new entry to the history file."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        entries = self.load_entries()
        entries.append(entry.to_dict())
        self.history_file.write_text(
            json.dumps(entries, indent=2) + "\n",
            encoding="utf-8",
        )

    @contextmanager
    def track_operation(
        self,
        operation: str,
        release: str,
        commit_sha: str,
        slo_target_seconds: float | None = None,
        details: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> Generator[dict[str, Any], None, None]:
        """Context manager to measure start/end time and record outcome to history."""
        started_at = datetime.now(UTC).isoformat()
        start_mono = monotonic()
        op_details: dict[str, Any] = dict(details or {})

        try:
            yield op_details
            ended_at = datetime.now(UTC).isoformat()
            duration = round(monotonic() - start_mono, 2)
            slo_met = (duration <= slo_target_seconds) if slo_target_seconds is not None else None

            if not dry_run:
                self.append_entry(
                    HistoryEntry(
                        operation=operation,
                        release=release,
                        commit_sha=commit_sha,
                        status="success",
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_seconds=duration,
                        slo_met=slo_met,
                        details=op_details,
                    )
                )
        except Exception as exc:
            ended_at = datetime.now(UTC).isoformat()
            duration = round(monotonic() - start_mono, 2)
            slo_met = False if slo_target_seconds is not None else None

            if not dry_run:
                self.append_entry(
                    HistoryEntry(
                        operation=operation,
                        release=release,
                        commit_sha=commit_sha,
                        status="failed",
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_seconds=duration,
                        error=str(exc),
                        slo_met=slo_met,
                        details=op_details,
                    )
                )
            raise
