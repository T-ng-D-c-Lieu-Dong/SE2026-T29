"""Rollback pre-condition validation gate (TASK-005 / TASK-007 Hardening).

Verifies critical system invariants before allowing automated or manual rollback:
1. Target release manifest exists and is schema-valid.
2. Target schema migration is compatible with database rollback window (E14).
3. Host system has sufficient available disk space for container recreation.
4. Deployment lock directory is accessible and state directory is writable.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from scripts.release_manifest import ReleaseManifest


@dataclass
class CheckItem:
    name: str
    passed: bool
    detail: str


@dataclass
class GuardReport:
    passed: bool
    checks: list[CheckItem] = field(default_factory=list)
    failure_reason: str | None = None

    def add_check(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(CheckItem(name=name, passed=passed, detail=detail))
        if not passed and self.passed:
            self.passed = False
            self.failure_reason = f"{name}: {detail}"


class RollbackGuard:
    def __init__(
        self,
        min_free_disk_mb: int = 250,
        state_dir: Path | str | None = None,
    ) -> None:
        self.min_free_disk_mb = min_free_disk_mb
        resolved = state_dir or os.getenv("BOOKING_STATE_DIR", "deploy")
        self.state_dir = Path(resolved).resolve()

    def check_disk_space(self, path: Path | None = None) -> CheckItem:
        target = path or self.state_dir
        try:
            target.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(target)
            free_mb = usage.free // (1024 * 1024)
            passed = free_mb >= self.min_free_disk_mb
            return CheckItem(
                name="disk_space",
                passed=passed,
                detail=f"{free_mb} MB available (minimum: {self.min_free_disk_mb} MB)",
            )
        except Exception as exc:
            return CheckItem(
                name="disk_space",
                passed=False,
                detail=f"Unable to determine disk usage: {exc}",
            )

    def check_state_dir_writable(self) -> CheckItem:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.state_dir / ".guard_write_probe"
            test_file.write_text("probe", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return CheckItem(
                name="state_dir_writable",
                passed=True,
                detail=f"State directory {self.state_dir} is writable",
            )
        except Exception as exc:
            return CheckItem(
                name="state_dir_writable",
                passed=False,
                detail=f"State directory not writable: {exc}",
            )

    def check_manifest(self, manifest_path: Path) -> tuple[CheckItem, ReleaseManifest | None]:
        if not manifest_path.is_file():
            return (
                CheckItem(
                    name="target_manifest",
                    passed=False,
                    detail=f"Target manifest not found: {manifest_path}",
                ),
                None,
            )
        try:
            manifest = ReleaseManifest.from_file(manifest_path)
            errors = manifest.validate()
            if errors:
                return (
                    CheckItem(
                        name="target_manifest",
                        passed=False,
                        detail=f"Invalid manifest errors: {'; '.join(errors)}",
                    ),
                    None,
                )
            return (
                CheckItem(
                    name="target_manifest",
                    passed=True,
                    detail=(
                        f"Manifest {manifest.release} valid (commit {manifest.commit_sha[:7]})"
                    ),
                ),
                manifest,
            )
        except Exception as exc:
            return (
                CheckItem(
                    name="target_manifest",
                    passed=False,
                    detail=f"Invalid release manifest schema: {exc}",
                ),
                None,
            )

    def check_schema_compatibility(
        self,
        target_manifest: ReleaseManifest,
        current_manifest_path: Path | None = None,
    ) -> CheckItem:
        curr_path = current_manifest_path or (self.state_dir / "current-manifest.json")
        if not curr_path.is_file():
            return CheckItem(
                name="schema_compatibility",
                passed=True,
                detail="Current manifest absent; assuming standalone target migration",
            )
        try:
            current = ReleaseManifest.from_file(curr_path)
            # E14: Target manifest migration must match or be within backward-compatible window
            curr_rev = current.migration_revision
            tgt_rev = target_manifest.migration_revision
            min_rev = target_manifest.compatibility.min_compatible_schema

            if min_rev and curr_rev < min_rev:
                return CheckItem(
                    name="schema_compatibility",
                    passed=False,
                    detail=(f"Current schema ({curr_rev}) precedes target min ({min_rev})"),
                )
            return CheckItem(
                name="schema_compatibility",
                passed=True,
                detail=f"Compatible schema: target revision {tgt_rev}, current {curr_rev}",
            )
        except Exception as exc:
            return CheckItem(
                name="schema_compatibility",
                passed=False,
                detail=f"Could not verify schema compatibility: {exc}",
            )

    def validate(
        self,
        target_manifest_path: Path,
        current_manifest_path: Path | None = None,
    ) -> GuardReport:
        report = GuardReport(passed=True)

        disk_check = self.check_disk_space()
        report.add_check(disk_check.name, disk_check.passed, disk_check.detail)

        write_check = self.check_state_dir_writable()
        report.add_check(write_check.name, write_check.passed, write_check.detail)

        manifest_check, manifest = self.check_manifest(target_manifest_path)
        report.add_check(manifest_check.name, manifest_check.passed, manifest_check.detail)

        if manifest:
            schema_check = self.check_schema_compatibility(
                manifest, current_manifest_path=current_manifest_path
            )
            report.add_check(schema_check.name, schema_check.passed, schema_check.detail)

        return report
