"""Deployment lock manager to prevent concurrent deployments or rollbacks.

Implements TASK-005 requirement:
- "Viết deploy và rollback scripts có khóa chống chạy đồng thời."
- Ensures mutual exclusion for environment mutations.
- Detects and cleans up stale locks if a previous process crashed.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import psutil


class DeploymentLockError(RuntimeError):
    """Raised when another deploy or rollback operation currently holds the lock."""


@dataclass
class LockMetadata:
    pid: int
    operation: str
    acquired_at: str
    target_release: str | None = None
    host: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> LockMetadata:
        data = json.loads(text)
        return cls(**data)


class DeploymentLock(AbstractContextManager["DeploymentLock"]):
    """Mutex lock for deploy and rollback operations.

    Uses atomic directory creation (POSIX and Windows both support atomic mkdir).
    Writes metadata.json inside the lock directory.
    """

    def __init__(
        self,
        lock_dir: Path | str = "deploy/.deploy.lock",
        timeout_seconds: float = 0.0,
        stale_timeout_seconds: float = 600.0,
        operation: str = "deploy",
        target_release: str | None = None,
    ) -> None:
        self.lock_dir = Path(lock_dir).resolve()
        self.metadata_file = self.lock_dir / "lock_metadata.json"
        self.timeout_seconds = timeout_seconds
        self.stale_timeout_seconds = stale_timeout_seconds
        self.operation = operation
        self.target_release = target_release
        self.is_acquired = False

    def _is_pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        return psutil.pid_exists(pid)

    def _inspect_existing_lock(self) -> LockMetadata | None:
        if not self.lock_dir.exists():
            return None
        if self.metadata_file.exists():
            try:
                content = self.metadata_file.read_text(encoding="utf-8")
                return LockMetadata.from_json(content)
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                return None
        return None

    def _cleanup_stale_lock(self, meta: LockMetadata | None) -> bool:
        """Removes the lock if the holding process is dead or exceeded stale timeout."""
        if not self.lock_dir.exists():
            return True

        is_stale = False
        reason = ""

        if meta is None:
            # Metadata missing or unparseable
            is_stale = True
            reason = "Lock directory exists but metadata is unreadable"
        else:
            # Check process liveness
            if not self._is_pid_alive(meta.pid):
                is_stale = True
                reason = f"Process with PID {meta.pid} is no longer running"
            else:
                # Check duration
                try:
                    acquired_dt = datetime.fromisoformat(meta.acquired_at)
                    now_dt = datetime.now(UTC)
                    age_seconds = (now_dt - acquired_dt).total_seconds()
                    if age_seconds > self.stale_timeout_seconds:
                        is_stale = True
                        reason = (
                            f"Lock aged {age_seconds:.0f}s exceeding limit of "
                            f"{self.stale_timeout_seconds}s"
                        )
                except (ValueError, TypeError):
                    pass

        if is_stale:
            try:
                if reason:
                    print(f"Cleaning up stale deployment lock: {reason}", file=sys.stderr)
                if self.metadata_file.exists():
                    self.metadata_file.unlink()
                self.lock_dir.rmdir()
                return True
            except OSError:
                return False
        return False

    def acquire(self) -> None:
        start_time = time.monotonic()
        while True:
            try:
                # mkdir is atomic on both POSIX and Windows filesystems
                self.lock_dir.parent.mkdir(parents=True, exist_ok=True)
                self.lock_dir.mkdir(parents=False, exist_ok=False)

                # Write metadata
                meta = LockMetadata(
                    pid=os.getpid(),
                    operation=self.operation,
                    acquired_at=datetime.now(UTC).isoformat(),
                    target_release=self.target_release,
                    host=platform.node(),
                )
                self.metadata_file.write_text(meta.to_json(), encoding="utf-8")
                self.is_acquired = True
                return
            except FileExistsError:
                # Check existing lock
                existing = self._inspect_existing_lock()
                cleaned = self._cleanup_stale_lock(existing)
                if cleaned:
                    continue  # Retry acquiring immediately

                elapsed = time.monotonic() - start_time
                if elapsed >= self.timeout_seconds:
                    pid_info = f"PID {existing.pid}" if existing else "unknown process"
                    op_info = f"doing '{existing.operation}'" if existing else "operation"
                    time_info = f"since {existing.acquired_at}" if existing else "unknown time"
                    msg = (
                        f"Cannot acquire deployment lock: held by {pid_info} "
                        f"{op_info} {time_info}. Concurrent deployments are forbidden."
                    )
                    raise DeploymentLockError(msg) from None
                time.sleep(0.5)

    def release(self) -> None:
        if not self.is_acquired:
            return
        try:
            if self.metadata_file.exists():
                self.metadata_file.unlink()
            if self.lock_dir.exists():
                self.lock_dir.rmdir()
        except OSError as exc:
            print(f"Warning: Failed to cleanly remove lock dir: {exc}", file=sys.stderr)
        finally:
            self.is_acquired = False

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.release()
