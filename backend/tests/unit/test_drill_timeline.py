"""Unit tests for drill timeline recorder (TASK-007 / C134)."""

from datetime import UTC, datetime, timedelta

from pathlib import Path

from scripts.drill_timeline import DrillTimeline, default_timeline_path, main

T0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)


def test_record_events_and_ordering():
    timeline = DrillTimeline(drill_id="test-drill-01")
    timeline.record_event("drill_start", "Deploy v0.2.0-drill", now=T0)
    timeline.record_event("alert_fired", "Alertmanager fired", now=T0 + timedelta(seconds=75))
    timeline.record_event(
        "investigation_start", "Check Tempo/Loki", now=T0 + timedelta(seconds=120)
    )
    timeline.record_event("rollback_start", "Trigger rollback", now=T0 + timedelta(seconds=160))
    timeline.record_event("rollback_complete", "Smoke test pass", now=T0 + timedelta(seconds=280))
    timeline.record_event("service_restored", "Fully healthy", now=T0 + timedelta(seconds=300))

    assert len(timeline.events) == 6
    assert timeline.get_event("drill_start").description == "Deploy v0.2.0-drill"
    assert timeline.get_event("non_existent") is None

    # Rollback duration: 280 - 160 = 120s (2 minutes)
    assert timeline.rollback_duration_seconds() == 120.0
    assert timeline.meets_rollback_target(300.0) is True
    assert timeline.meets_rollback_target(100.0) is False

    # MTTR: 300 - 0 = 300s (5 minutes)
    assert timeline.mttr_seconds() == 300.0


def test_timeline_persistence_round_trip(tmp_path):
    target = tmp_path / "drill-timeline.json"
    timeline = DrillTimeline(drill_id="round-trip-01")
    timeline.record_event("drill_start", "Starting drill", now=T0)
    timeline.record_event("rollback_start", "Rollback", now=T0 + timedelta(minutes=2))
    timeline.record_event("rollback_complete", "Done", now=T0 + timedelta(minutes=4))
    timeline.save(target)

    assert target.is_file()
    restored = DrillTimeline.load(target)
    assert restored.drill_id == "round-trip-01"
    assert len(restored.events) == 3
    assert restored.rollback_duration_seconds() == 120.0
    assert restored.meets_rollback_target() is True


def test_timeline_markdown_table():
    timeline = DrillTimeline(drill_id="table-test")
    timeline.record_event("drill_start", "Start", now=T0)
    timeline.record_event("alert_fired", "Alert", now=T0 + timedelta(seconds=60))
    table = timeline.to_markdown_table()

    assert "| Event | Timestamp (UTC) | Relative | Description |" in table
    assert "`drill_start`" in table
    assert "`alert_fired`" in table
    assert "+60s" in table


def test_missing_events_handled_gracefully():
    timeline = DrillTimeline(drill_id="empty")
    assert timeline.rollback_duration_seconds() is None
    assert timeline.mttr_seconds() is None
    assert timeline.meets_rollback_target() is False
    assert "| Event |" in timeline.to_markdown_table()


def test_timeline_cli_flow(tmp_path, monkeypatch, capsys):
    timeline_file = tmp_path / "cli-timeline.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "drill_timeline.py",
            "record",
            "--event",
            "drill_start",
            "--description",
            "Test Start",
            "--file",
            str(timeline_file),
        ],
    )
    main()
    assert timeline_file.is_file()

    monkeypatch.setattr(
        "sys.argv",
        [
            "drill_timeline.py",
            "record",
            "--event",
            "rollback_complete",
            "--file",
            str(timeline_file),
        ],
    )
    main()

    monkeypatch.setattr("sys.argv", ["drill_timeline.py", "report", "--file", str(timeline_file)])
    main()
    out = capsys.readouterr().out
    assert "drill-demo" in out
    assert "`drill_start`" in out

    monkeypatch.setattr("sys.argv", ["drill_timeline.py", "clear", "--file", str(timeline_file)])
    main()
    assert not timeline_file.exists()


def test_default_timeline_path_resolution(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKING_STATE_DIR", raising=False)
    assert default_timeline_path() == Path("deploy/drill-timeline.json")

    monkeypatch.setenv("BOOKING_STATE_DIR", str(tmp_path / "custom"))
    assert default_timeline_path() == tmp_path / "custom" / "drill-timeline.json"

