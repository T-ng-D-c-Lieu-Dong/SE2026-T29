from pathlib import Path

import pytest
from scripts.deploy_history import DeploymentHistory, HistoryEntry


def test_history_entry_serialization():
    entry = HistoryEntry(
        operation="deploy",
        release="v0.1.0",
        commit_sha="abcd1234efgh5678",
        status="success",
        started_at="2026-10-23T08:00:00+00:00",
        ended_at="2026-10-23T08:00:02+00:00",
        duration_seconds=2.0,
        slo_met=True,
    )
    d = entry.to_dict()
    assert d["operation"] == "deploy"
    assert d["release"] == "v0.1.0"
    assert d["duration_seconds"] == 2.0
    assert d["slo_met"] is True
    assert "error" not in d
    assert "details" not in d


def test_history_load_missing_or_corrupt_file(tmp_path: Path):
    history = DeploymentHistory(state_dir=tmp_path)
    assert history.load_entries() == []

    # Corrupt content
    history.history_file.write_text("invalid json content!", encoding="utf-8")
    assert history.load_entries() == []

    # Non-list JSON
    history.history_file.write_text('{"not": "a list"}', encoding="utf-8")
    assert history.load_entries() == []


def test_history_append_and_load(tmp_path: Path):
    history = DeploymentHistory(state_dir=tmp_path)
    entry1 = HistoryEntry(
        operation="deploy",
        release="v0.1.0",
        commit_sha="1111",
        status="success",
        started_at="2026-10-23T08:00:00+00:00",
        ended_at="2026-10-23T08:00:01+00:00",
        duration_seconds=1.0,
    )
    history.append_entry(entry1)

    entries = history.load_entries()
    assert len(entries) == 1
    assert entries[0]["release"] == "v0.1.0"

    entry2 = HistoryEntry(
        operation="rollback",
        release="v0.1.0",
        commit_sha="1111",
        status="success",
        started_at="2026-10-23T08:05:00+00:00",
        ended_at="2026-10-23T08:05:01+00:00",
        duration_seconds=0.8,
        slo_met=True,
    )
    history.append_entry(entry2)

    entries_after = history.load_entries()
    assert len(entries_after) == 2
    assert entries_after[1]["operation"] == "rollback"


def test_track_operation_context_manager_handles_exception(tmp_path: Path):
    history = DeploymentHistory(state_dir=tmp_path)

    with pytest.raises(ValueError, match="Deployment failure test"):
        with history.track_operation(
            operation="deploy",
            release="v0.2.0",
            commit_sha="2222",
            slo_target_seconds=300.0,
        ):
            raise ValueError("Deployment failure test")

    entries = history.load_entries()
    assert len(entries) == 1
    assert entries[0]["operation"] == "deploy"
    assert entries[0]["status"] == "failed"
    assert "Deployment failure test" in entries[0]["error"]
    assert entries[0]["slo_met"] is False
