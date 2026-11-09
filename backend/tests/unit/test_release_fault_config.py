import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.fault_config import FaultConfig
from scripts.release_manifest import ReleaseManifest, main

NOW = datetime(2026, 11, 2, 3, 0, tzinfo=UTC)
REFERENCE = Path(__file__).resolve().parents[3] / "docs/releases/v0.1.0.json"


def test_legacy_manifest_disables_faults_explicitly():
    manifest = ReleaseManifest.load(REFERENCE)
    assert manifest.fault == FaultConfig()
    assert manifest.fault.to_environment()["BOOKING_FAULT_MODE"] == "off"
    assert manifest.fault.to_environment()["BOOKING_FAULT_UNTIL"] == ""


def test_fault_duration_starts_at_deploy_and_does_not_restart_on_rollback():
    planned = FaultConfig(mode="error", rate=0.25, duration_seconds=900)
    with pytest.raises(ValueError, match="activated and recorded"):
        planned.to_environment()
    active = planned.activate(NOW)
    assert active.until == (NOW + timedelta(minutes=15)).isoformat()
    assert active.is_active(NOW)
    assert not active.is_active(NOW + timedelta(minutes=15))
    assert active.activate(NOW + timedelta(minutes=5)) == active
    assert planned.until is None


def test_fault_manifest_round_trip_preserves_recorded_expiry(tmp_path):
    manifest = ReleaseManifest.load(REFERENCE)
    manifest.fault = FaultConfig(mode="latency", rate=0.5, duration_seconds=60).activate(NOW)
    target = tmp_path / "drill.json"
    manifest.save(target)
    restored = ReleaseManifest.load(target)
    assert restored.fault == manifest.fault
    env = restored.fault.to_environment()
    assert env["BOOKING_FAULT_MODE"] == "latency"
    assert env["BOOKING_FAULT_RATE"] == "0.5"
    assert env["BOOKING_FAULT_UNTIL"] == (NOW + timedelta(minutes=1)).isoformat()
    assert env["BOOKING_FAULT_LATENCY_SECONDS"] == "3.0"


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "invalid"},
        {"mode": "error"},
        {"rate": -0.1},
        {"rate": 1.1},
        {"rate": "0.5"},
        {"rate": True},
        {"rate": float("nan")},
        {"latency_seconds": float("inf")},
        {"latency_seconds": -1},
        {"latency_seconds": 31},
        {"latency_seconds": False},
        {"duration_seconds": 0},
        {"duration_seconds": 3601},
        {"duration_seconds": 1.5},
        {"duration_seconds": True},
        {"until": "2026-11-02T03:00:00"},
        {"until": "not-a-time"},
        {"until": "2026-11-02T03:00:00+00:00\nBOOKING_FAULT_MODE=off"},
    ],
)
def test_invalid_fault_config_is_rejected_before_env_write(changes, tmp_path):
    manifest = ReleaseManifest.load(REFERENCE)
    manifest.fault = replace(FaultConfig(), **changes)
    assert manifest.validate()
    with pytest.raises(ValueError):
        manifest.save(tmp_path / "invalid.json")
    assert not (tmp_path / "invalid.json").exists()


def test_manifest_cli_includes_fault_config(tmp_path, monkeypatch):
    config = tmp_path / "fault.json"
    config.write_text(json.dumps({"mode": "error", "rate": 0.2, "duration_seconds": 900}))
    output = tmp_path / "manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "release_manifest",
            "create",
            "--release",
            "v0.2.0-drill",
            "--commit-sha",
            "abcdef1",
            "--migration-revision",
            "20261007_0001",
            "--backend-digest",
            "sha256:" + "a" * 64,
            "--fault-config",
            str(config),
            "--output",
            str(output),
        ],
    )
    main()
    manifest = ReleaseManifest.load(output)
    assert manifest.fault == FaultConfig(mode="error", rate=0.2, duration_seconds=900)


def test_deploy_activates_fault_and_rollback_clears_it_without_migration(tmp_path):
    from unittest.mock import patch

    from scripts.deploy import Deployer
    from scripts.rollback import Rollbacker

    state = tmp_path / "state"
    healthy = ReleaseManifest.load(REFERENCE)
    baseline = tmp_path / "healthy.json"
    healthy.save(baseline)
    Deployer(baseline, state_dir=state, skip_container_ops=True).run()

    drill = replace(
        healthy,
        release="v0.2.0-drill",
        fault=FaultConfig(
            mode="error",
            rate=0.2,
            duration_seconds=900,
        ),
    )
    target = tmp_path / "drill.json"
    drill.save(target)
    deployer = Deployer(target, state_dir=state, skip_container_ops=True)
    deployer.run()
    active = ReleaseManifest.load(state / "current-manifest.json")
    assert active.fault.until is not None
    assert active.fault.is_active()
    env = (state / ".env.production").read_text()
    for key, value in active.fault.to_environment().items():
        assert f"{key}={value}\n" in env

    rollbacker = Rollbacker(state_dir=state)
    with (
        patch.object(rollbacker, "execute_command") as execute,
        patch.object(rollbacker, "run_smoke_tests", return_value=True),
    ):
        rollbacker.run()
    commands = [call.args[0] for call in execute.call_args_list]
    assert len(commands) == 1
    assert commands[0][-3:] == ["up", "-d", "--remove-orphans"]
    assert all("migrate" not in command and "downgrade" not in command for command in commands)
    restored = ReleaseManifest.load(state / "current-manifest.json")
    assert restored.release == healthy.release
    env = (state / ".env.production").read_text()
    assert "BOOKING_FAULT_MODE=off\n" in env
    assert "BOOKING_FAULT_UNTIL=\n" in env


@pytest.mark.parametrize("mode", ["error", "latency"])
def test_active_drill_smoke_keeps_readiness_and_version_but_skips_business(tmp_path, mode):
    from unittest.mock import patch

    from scripts.deploy import Deployer
    from scripts.smoke_test import SmokeTestRunner

    manifest = ReleaseManifest.load(REFERENCE)
    manifest.fault = FaultConfig(mode=mode, duration_seconds=900).activate()
    deployer = Deployer(REFERENCE, state_dir=tmp_path)
    replies = [
        (200, {"status": "ready"}),
        (
            200,
            {
                "release": manifest.release,
                "commit_sha": manifest.commit_sha,
            },
        ),
    ]
    with patch.object(SmokeTestRunner, "_http_request", side_effect=replies) as request:
        assert deployer.run_smoke_tests(manifest)
    assert [call.args[1] for call in request.call_args_list] == ["/health/ready", "/api/version"]


def test_drill_smoke_still_rejects_wrong_release(tmp_path):
    from unittest.mock import patch

    from scripts.deploy import Deployer
    from scripts.smoke_test import SmokeTestRunner

    manifest = ReleaseManifest.load(REFERENCE)
    manifest.fault = FaultConfig(mode="error", duration_seconds=60).activate()
    replies = [(200, {}), (200, {"release": "wrong", "commit_sha": manifest.commit_sha})]
    with patch.object(SmokeTestRunner, "_http_request", side_effect=replies):
        assert not Deployer(REFERENCE, state_dir=tmp_path).run_smoke_tests(manifest)


def test_expired_drill_runs_full_business_smoke(tmp_path):
    from unittest.mock import patch

    from scripts.deploy import Deployer
    from scripts.smoke_test import SmokeTestResult, SmokeTestRunner

    manifest = ReleaseManifest.load(REFERENCE)
    manifest.fault = FaultConfig(
        mode="error", until=(datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    )
    result = SmokeTestResult(True, "business_flow", 0.1, "ok", {})
    with patch.object(SmokeTestRunner, "run_all", return_value=[result]) as run:
        assert Deployer(REFERENCE, state_dir=tmp_path).run_smoke_tests(manifest)
        run.assert_called_once()


def test_generated_env_matches_backend_fault_settings(tmp_path, monkeypatch):
    from scripts.deploy import Deployer

    from app.config import Settings

    manifest = ReleaseManifest.load(REFERENCE)
    manifest.fault = FaultConfig(
        mode="latency", rate=0.25, duration_seconds=60, latency_seconds=1.5
    )
    Deployer(REFERENCE, state_dir=tmp_path).prepare_environment_file(manifest)
    for line in (tmp_path / ".env.production").read_text().splitlines():
        if line.startswith("BOOKING_FAULT_"):
            key, value = line.split("=", 1)
            monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    assert settings.fault_mode == "latency"
    assert settings.fault_rate == 0.25
    assert settings.fault_latency_seconds == 1.5
    assert settings.fault_until == datetime.fromisoformat(manifest.fault.until)
