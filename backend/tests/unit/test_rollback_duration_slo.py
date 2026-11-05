"""Unit tests for rollback duration SLO verification against 5-minute target (TASK-007 / C185)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.deploy_history import DeploymentHistory, HistoryEntry
from scripts.drill_timeline import DrillTimeline
from scripts.verify_rollback_slo import (
    RollbackSloResult,
    evaluate_rollback_slo,
    main,
)

T0 = datetime(2026, 11, 2, 14, 0, 0, tzinfo=UTC)


def test_evaluate_slo_from_history_passing(tmp_path: Path):
    history = DeploymentHistory(state_dir=tmp_path)
    entry = HistoryEntry(
        operation="rollback",
        release="v0.2.0",
        commit_sha="abcdef1234567890",
        status="success",
        started_at=T0.isoformat(),
        ended_at=(T0 + timedelta(seconds=38.4)).isoformat(),
        duration_seconds=38.4,
        slo_met=True,
    )
    history.append_entry(entry)

    res = evaluate_rollback_slo(state_dir=tmp_path, target_seconds=300.0)
    assert isinstance(res, RollbackSloResult)
    assert res.operation == "rollback"
    assert res.release == "v0.2.0"
    assert res.duration_seconds == 38.4
    assert res.target_seconds == 300.0
    assert res.slo_met is True
    assert res.margin_seconds == 261.6
    assert "history:" in res.source
    assert "[PASS]" in res.summary_text()


def test_evaluate_slo_from_history_failing(tmp_path: Path):
    history = DeploymentHistory(state_dir=tmp_path)
    entry = HistoryEntry(
        operation="rollback",
        release="v0.2.0",
        commit_sha="abcdef1234567890",
        status="success",
        started_at=T0.isoformat(),
        ended_at=(T0 + timedelta(seconds=350.0)).isoformat(),
        duration_seconds=350.0,
        slo_met=False,
    )
    history.append_entry(entry)

    res = evaluate_rollback_slo(state_dir=tmp_path, target_seconds=300.0)
    assert res.slo_met is False
    assert res.duration_seconds == 350.0
    assert res.margin_seconds == -50.0
    assert "[FAIL]" in res.summary_text()


def test_evaluate_slo_fallback_to_timeline(tmp_path: Path):
    empty_history = tmp_path / "deploy"
    timeline_file = tmp_path / "drill-timeline.json"

    timeline = DrillTimeline(drill_id="drill-rehearsal-01")
    timeline.record_event("drill_start", "Start", now=T0)
    timeline.record_event("rollback_start", "Start rollback", now=T0 + timedelta(minutes=2))
    timeline.record_event(
        "rollback_complete", "Finish rollback", now=T0 + timedelta(minutes=2, seconds=45)
    )
    timeline.save(timeline_file)

    res = evaluate_rollback_slo(
        state_dir=empty_history,
        timeline_file=timeline_file,
        target_seconds=300.0,
    )
    assert res.duration_seconds == 45.0
    assert res.slo_met is True
    assert res.margin_seconds == 255.0
    assert res.release == "drill-rehearsal-01"
    assert "timeline:" in res.source


def test_evaluate_slo_no_data_raises_error(tmp_path: Path):
    empty_history = tmp_path / "deploy"
    empty_timeline = tmp_path / "non-existent-timeline.json"

    with pytest.raises(ValueError, match="No rollback operations found"):
        evaluate_rollback_slo(state_dir=empty_history, timeline_file=empty_timeline)


def test_cli_json_output(tmp_path: Path, monkeypatch, capsys):
    history = DeploymentHistory(state_dir=tmp_path)
    history.append_entry(
        HistoryEntry(
            operation="rollback",
            release="v0.2.0",
            commit_sha="12345678",
            status="success",
            started_at=T0.isoformat(),
            ended_at=(T0 + timedelta(seconds=40)).isoformat(),
            duration_seconds=40.0,
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_rollback_slo.py",
            "--state-dir",
            str(tmp_path),
            "--json",
        ],
    )
    main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["operation"] == "rollback"
    assert data["duration_seconds"] == 40.0
    assert data["slo_met"] is True


def test_cli_fail_on_violation_exits(tmp_path: Path, monkeypatch):
    history = DeploymentHistory(state_dir=tmp_path)
    history.append_entry(
        HistoryEntry(
            operation="rollback",
            release="v0.2.0",
            commit_sha="12345678",
            status="success",
            started_at=T0.isoformat(),
            ended_at=(T0 + timedelta(seconds=400)).isoformat(),
            duration_seconds=400.0,
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_rollback_slo.py",
            "--state-dir",
            str(tmp_path),
            "--target-seconds",
            "300.0",
            "--fail-on-violation",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
