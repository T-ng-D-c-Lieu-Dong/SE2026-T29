"""Unit tests for automated rollback validation gate (TASK-005 / TASK-007 Hardening)."""

from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from scripts.release_manifest import ReleaseManifest
from scripts.rollback_guard import RollbackGuard

Usage = namedtuple("Usage", ["total", "used", "free"])


def test_disk_space_check(tmp_path: Path):
    guard = RollbackGuard(min_free_disk_mb=500, state_dir=tmp_path)

    # 1. Sufficient disk space
    with patch(
        "shutil.disk_usage", return_value=Usage(total=10**10, used=10**9, free=1024 * 1024 * 600)
    ):
        res = guard.check_disk_space()
        assert res.passed is True
        assert "600 MB available" in res.detail

    # 2. Insufficient disk space
    with patch(
        "shutil.disk_usage", return_value=Usage(total=10**10, used=10**9, free=1024 * 1024 * 100)
    ):
        res = guard.check_disk_space()
        assert res.passed is False
        assert "100 MB available" in res.detail


def test_state_dir_writable_check(tmp_path: Path):
    valid_dir = tmp_path / "valid_state"
    guard = RollbackGuard(state_dir=valid_dir)
    res = guard.check_state_dir_writable()
    assert res.passed is True

    # Non-writable path
    with patch.object(Path, "write_text", side_effect=PermissionError("Permission denied")):
        res_fail = guard.check_state_dir_writable()
        assert res_fail.passed is False
        assert "Permission denied" in res_fail.detail


def test_manifest_validation(tmp_path: Path):
    guard = RollbackGuard(state_dir=tmp_path)

    # 1. Missing manifest
    missing_path = tmp_path / "non_existent.json"
    check, manifest = guard.check_manifest(missing_path)
    assert check.passed is False
    assert manifest is None

    # 2. Valid manifest
    valid_path = Path("docs/releases/v0.2.1.json")
    check, manifest = guard.check_manifest(valid_path)
    assert check.passed is True
    assert manifest is not None
    assert manifest.release == "v0.2.1"


def test_schema_compatibility_check(tmp_path: Path):
    guard = RollbackGuard(state_dir=tmp_path)
    target = ReleaseManifest.load(Path("docs/releases/v0.2.1.json"))

    # Compatible revision
    curr_manifest_path = tmp_path / "curr.json"
    curr_manifest_path.write_text(target.to_json(), encoding="utf-8")
    check = guard.check_schema_compatibility(target, current_manifest_path=curr_manifest_path)
    assert check.passed is True


def test_full_guard_pipeline(tmp_path: Path):
    guard = RollbackGuard(min_free_disk_mb=100, state_dir=tmp_path)
    target = Path("docs/releases/v0.2.1.json")
    report = guard.validate(target_manifest_path=target)

    assert report.passed is True
    assert len(report.checks) == 4
    assert all(c.passed for c in report.checks)
