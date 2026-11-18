"""Unit tests for database snapshot manager (TASK-005 / TASK-007 Hardening)."""

from pathlib import Path

from scripts.db_snapshot import DatabaseSnapshotManager


def test_db_snapshot_dry_run(tmp_path: Path):
    mgr = DatabaseSnapshotManager(backup_dir=tmp_path)
    output = mgr.create_dump(prefix="test_snap", dry_run=True)

    assert output.is_file()
    assert "test_snap" in output.name
    content = output.read_text(encoding="utf-8")
    assert "DRY-RUN DUMP" in content


def test_db_snapshot_list_and_verify(tmp_path: Path):
    mgr = DatabaseSnapshotManager(backup_dir=tmp_path)
    file1 = tmp_path / "snap1.sql"
    file1.write_text("-- PostgreSQL database dump\nSELECT 1;\n", encoding="utf-8")

    items = mgr.list_snapshots()
    assert len(items) == 1
    assert items[0].filename == "snap1.sql"
    assert items[0].size_bytes > 0

    assert mgr.verify_dump(file1) is True

    # Empty file
    empty_file = tmp_path / "empty.sql"
    empty_file.write_text("", encoding="utf-8")
    assert mgr.verify_dump(empty_file) is False
