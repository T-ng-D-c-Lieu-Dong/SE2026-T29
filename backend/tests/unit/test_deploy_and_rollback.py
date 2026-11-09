from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scripts.deploy import Deployer, build_compose_up_command
from scripts.release_manifest import ImageSpec, ReleaseManifest
from scripts.rollback import Rollbacker
from scripts.smoke_test import SmokeTestResult, SmokeTestRunner

DIGEST_V1 = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
DIGEST_V2 = "sha256:2222222222222222222222222222222222222222222222222222222222222222"


def test_build_compose_up_command_produces_deterministic_args():
    env_file = Path("/opt/booking/state/.env.production")
    compose_file = Path("deploy/compose.production.yaml")
    cmd = build_compose_up_command(env_file, compose_file)

    assert cmd == [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(compose_file),
        "up",
        "-d",
        "--remove-orphans",
    ]


def test_build_compose_up_command_custom_flags():
    cmd = build_compose_up_command("env.txt", "compose.yaml", detach=False, remove_orphans=False)
    assert cmd == ["docker", "compose", "--env-file", "env.txt", "-f", "compose.yaml", "up"]


@pytest.fixture
def v1_manifest(tmp_path: Path) -> Path:
    manifest = ReleaseManifest(
        release="v0.1.0",
        commit_sha="1111111111111111111111111111111111111111",
        migration_revision="20261007_0001",
        images={
            "backend": ImageSpec(
                repository="ghcr.io/cuongmotnang/booking-backend",
                tag="v0.1.0",
                digest=DIGEST_V1,
            )
        },
    )
    p = tmp_path / "v0.1.0.json"
    manifest.save(p)
    return p


@pytest.fixture
def v2_manifest(tmp_path: Path) -> Path:
    manifest = ReleaseManifest(
        release="v0.2.0",
        commit_sha="2222222222222222222222222222222222222222",
        migration_revision="20261007_0001",
        images={
            "backend": ImageSpec(
                repository="ghcr.io/cuongmotnang/booking-backend",
                tag="v0.2.0",
                digest=DIGEST_V2,
            )
        },
    )
    p = tmp_path / "v0.2.0.json"
    manifest.save(p)
    return p


def test_deployer_prepares_pinned_env_file(tmp_path: Path, v1_manifest: Path):
    deploy_state = tmp_path / "deploy"
    deployer = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        dry_run=False,
        skip_container_ops=True,
    )
    manifest = ReleaseManifest.load(v1_manifest)
    deployer.prepare_environment_file(manifest)

    env_file = deploy_state / ".env.production"
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert f"BACKEND_IMAGE_REF=ghcr.io/cuongmotnang/booking-backend@{DIGEST_V1}" in content
    assert "BOOKING_RELEASE=v0.1.0" in content
    assert "BOOKING_COMMIT_SHA=1111111111111111111111111111111111111111" in content


def test_deploy_and_rollback_manifest_history_flow(
    tmp_path: Path, v1_manifest: Path, v2_manifest: Path
):
    deploy_state = tmp_path / "deploy"

    # Step 1: Deploy v0.1.0 successfully
    deployer_v1 = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer_v1.run()

    current_mf = deploy_state / "current-manifest.json"
    assert current_mf.exists()
    assert ReleaseManifest.load(current_mf).release == "v0.1.0"

    # Step 2: Deploy v0.2.0 successfully
    deployer_v2 = Deployer(
        manifest_path=v2_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer_v2.run()

    previous_mf = deploy_state / "previous-manifest.json"
    assert previous_mf.exists()
    assert ReleaseManifest.load(previous_mf).release == "v0.1.0"
    assert ReleaseManifest.load(current_mf).release == "v0.2.0"

    # Step 3: Trigger rollback to previous manifest
    rollbacker = Rollbacker(
        target_manifest=previous_mf,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    rollbacker.run()

    # Current manifest should now be restored to v0.1.0
    assert ReleaseManifest.load(current_mf).release == "v0.1.0"
    env_content = (deploy_state / ".env.production").read_text(encoding="utf-8")
    assert "BOOKING_RELEASE=v0.1.0" in env_content
    assert f"@{DIGEST_V1}" in env_content


def test_deploy_auto_rollbacks_on_smoke_test_failure(
    tmp_path: Path, v1_manifest: Path, v2_manifest: Path
):
    deploy_state = tmp_path / "deploy"

    # Deploy initial good release v0.1.0
    deployer_v1 = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer_v1.run()

    # Now attempt deploying v0.2.0, but simulate smoke test failure
    deployer_v2 = Deployer(
        manifest_path=v2_manifest,
        state_dir=deploy_state,
        skip_container_ops=False,  # Runs smoke tests
    )

    failed_result = [
        SmokeTestResult(
            success=False,
            step="readiness_check",
            duration_seconds=5.0,
            message="Readiness timed out",
            details={},
        )
    ]
    recovered_result = [
        SmokeTestResult(
            success=True,
            step="readiness_check",
            duration_seconds=1.0,
            message="Readiness ok",
            details={},
        ),
        SmokeTestResult(
            success=True,
            step="version_check",
            duration_seconds=0.5,
            message="Version ok",
            details={},
        ),
        SmokeTestResult(
            success=True,
            step="business_flow",
            duration_seconds=1.5,
            message="Flow ok",
            details={},
        ),
    ]

    # First call fails (deploy v2), second call succeeds (rollback to v1)
    with patch.object(SmokeTestRunner, "run_all", side_effect=[failed_result, recovered_result]):
        with patch.object(deployer_v2, "apply_migrations", MagicMock()):
            with patch.object(deployer_v2, "deploy_containers", MagicMock()):
                with patch.object(Rollbacker, "recreate_containers", MagicMock()):
                    with pytest.raises(RuntimeError) as exc_info:
                        deployer_v2.run()

    assert "Automatic rollback executed" in str(exc_info.value)

    # Verify state was safely rolled back to v0.1.0
    current_mf = deploy_state / "current-manifest.json"
    assert ReleaseManifest.load(current_mf).release == "v0.1.0"


def test_deployer_configurable_state_dir_explicit(tmp_path: Path, v1_manifest: Path):
    custom_state = tmp_path / "custom_state"
    deployer = Deployer(
        manifest_path=v1_manifest,
        state_dir=custom_state,
        skip_container_ops=True,
    )
    assert deployer.state_dir == custom_state.resolve()
    assert deployer.current_manifest_file == custom_state.resolve() / "current-manifest.json"
    assert deployer.previous_manifest_file == custom_state.resolve() / "previous-manifest.json"
    assert deployer.env_file == custom_state.resolve() / ".env.production"
    assert deployer.lock_dir == custom_state.resolve() / ".deploy.lock"


def test_deployer_configurable_state_dir_from_env(
    tmp_path: Path, v1_manifest: Path, monkeypatch: pytest.MonkeyPatch
):
    env_state = tmp_path / "env_state"
    monkeypatch.setenv("BOOKING_STATE_DIR", str(env_state))

    deployer = Deployer(manifest_path=v1_manifest, skip_container_ops=True)
    assert deployer.state_dir == env_state.resolve()
    assert deployer.current_manifest_file == env_state.resolve() / "current-manifest.json"
    assert deployer.env_file == env_state.resolve() / ".env.production"


def test_deployer_configurable_state_dir_default_fallback(
    v1_manifest: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("BOOKING_STATE_DIR", raising=False)
    deployer = Deployer(manifest_path=v1_manifest, skip_container_ops=True)
    assert deployer.state_dir == Path("deploy").resolve()


def test_rollbacker_configurable_state_dir_explicit(tmp_path: Path):
    custom_state = tmp_path / "custom_state"
    rollbacker = Rollbacker(
        state_dir=custom_state,
        skip_container_ops=True,
    )
    assert rollbacker.state_dir == custom_state.resolve()
    assert rollbacker.target_manifest_path == custom_state.resolve() / "previous-manifest.json"
    assert rollbacker.current_manifest_file == custom_state.resolve() / "current-manifest.json"
    assert rollbacker.env_file == custom_state.resolve() / ".env.production"
    assert rollbacker.lock_dir == custom_state.resolve() / ".deploy.lock"


def test_rollbacker_configurable_state_dir_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    env_state = tmp_path / "env_state"
    monkeypatch.setenv("BOOKING_STATE_DIR", str(env_state))

    rollbacker = Rollbacker(skip_container_ops=True)
    assert rollbacker.state_dir == env_state.resolve()
    assert rollbacker.target_manifest_path == env_state.resolve() / "previous-manifest.json"


def test_rollbacker_custom_target_manifest_overrides_state_dir(tmp_path: Path):
    custom_state = tmp_path / "custom_state"
    explicit_target = tmp_path / "custom_prev.json"

    rollbacker = Rollbacker(
        target_manifest=explicit_target,
        state_dir=custom_state,
        skip_container_ops=True,
    )
    assert rollbacker.state_dir == custom_state.resolve()
    assert rollbacker.target_manifest_path == explicit_target.resolve()


def test_deploy_records_history_entry_on_success(tmp_path: Path, v1_manifest: Path):
    deploy_state = tmp_path / "deploy"
    deployer = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer.run()

    assert deployer.history_file.exists()
    entries = deployer.history.load_entries()
    assert len(entries) == 1
    assert entries[0]["operation"] == "deploy"
    assert entries[0]["release"] == "v0.1.0"
    assert entries[0]["commit_sha"] == "1111111111111111111111111111111111111111"
    assert entries[0]["status"] == "success"
    assert "started_at" in entries[0]
    assert "ended_at" in entries[0]
    assert entries[0]["duration_seconds"] >= 0.0


def test_deploy_and_rollback_accumulate_history(
    tmp_path: Path, v1_manifest: Path, v2_manifest: Path
):
    deploy_state = tmp_path / "deploy"

    # Step 1: Deploy v1
    deployer_v1 = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer_v1.run()

    # Step 2: Deploy v2
    deployer_v2 = Deployer(
        manifest_path=v2_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer_v2.run()

    # Step 3: Rollback to v1
    previous_mf = deploy_state / "previous-manifest.json"
    rollbacker = Rollbacker(
        target_manifest=previous_mf,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    rollbacker.run()

    entries = deployer_v1.history.load_entries()
    assert len(entries) == 3
    assert entries[0]["operation"] == "deploy"
    assert entries[0]["release"] == "v0.1.0"
    assert entries[0]["status"] == "success"

    assert entries[1]["operation"] == "deploy"
    assert entries[1]["release"] == "v0.2.0"
    assert entries[1]["status"] == "success"

    assert entries[2]["operation"] == "rollback"
    assert entries[2]["release"] == "v0.1.0"
    assert entries[2]["status"] == "success"
    assert entries[2]["slo_met"] is True


def test_deploy_failure_records_failed_history_entry(
    tmp_path: Path, v1_manifest: Path, v2_manifest: Path
):
    deploy_state = tmp_path / "deploy"

    # Deploy good release v1
    deployer_v1 = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        skip_container_ops=True,
    )
    deployer_v1.run()

    # Deploy v2 with simulated smoke test failure
    deployer_v2 = Deployer(
        manifest_path=v2_manifest,
        state_dir=deploy_state,
        skip_container_ops=False,
    )

    failed_result = [
        SmokeTestResult(
            success=False,
            step="readiness_check",
            duration_seconds=5.0,
            message="Readiness timed out",
            details={},
        )
    ]
    recovered_result = [
        SmokeTestResult(
            success=True,
            step="readiness_check",
            duration_seconds=1.0,
            message="Readiness ok",
            details={},
        )
    ]

    with patch.object(SmokeTestRunner, "run_all", side_effect=[failed_result, recovered_result]):
        with patch.object(deployer_v2, "apply_migrations", MagicMock()):
            with patch.object(deployer_v2, "deploy_containers", MagicMock()):
                with patch.object(Rollbacker, "recreate_containers", MagicMock()):
                    with pytest.raises(RuntimeError):
                        deployer_v2.run()

    entries = deployer_v2.history.load_entries()
    # Expect entries for initial deploy, failed deploy, and auto-rollback
    assert len(entries) >= 2
    failed_deploy = next(
        e for e in entries if e["operation"] == "deploy" and e["release"] == "v0.2.0"
    )
    assert failed_deploy["status"] == "failed"
    assert "error" in failed_deploy
    assert "Automatic rollback executed" in failed_deploy["error"]


def test_dry_run_does_not_mutate_history_file(tmp_path: Path, v1_manifest: Path):
    deploy_state = tmp_path / "deploy"
    deployer = Deployer(
        manifest_path=v1_manifest,
        state_dir=deploy_state,
        dry_run=True,
        skip_container_ops=True,
    )
    deployer.run()

    assert not deployer.history_file.exists()


def test_apply_migrations_runs_migrate_service_from_release_image(
    tmp_path: Path, v1_manifest: Path
):
    deploy_state = tmp_path / "deploy"
    deployer = Deployer(manifest_path=v1_manifest, state_dir=deploy_state)
    manifest = ReleaseManifest.load(v1_manifest)

    with patch.object(deployer, "execute_command") as execute:
        deployer.apply_migrations(manifest)

    execute.assert_called_once_with(
        [
            "docker",
            "compose",
            "--env-file",
            str(deploy_state.resolve() / ".env.production"),
            "-f",
            str(deployer.compose_file),
            "--profile",
            "migrate",
            "run",
            "--rm",
            "migrate",
        ]
    )


DIGEST_WEB = "sha256:3333333333333333333333333333333333333333333333333333333333333333"


@pytest.fixture
def full_stack_manifest(tmp_path: Path) -> Path:
    manifest = ReleaseManifest(
        release="v0.3.0",
        commit_sha="3333333333333333333333333333333333333333",
        migration_revision="20261007_0001",
        images={
            "backend": ImageSpec(
                repository="ghcr.io/cuongmotnang/booking-backend",
                tag="v0.3.0",
                digest=DIGEST_V2,
            ),
            "frontend": ImageSpec(
                repository="ghcr.io/cuongmotnang/booking-frontend",
                tag="v0.3.0",
                digest=DIGEST_WEB,
            ),
        },
    )
    p = tmp_path / "v0.3.0.json"
    manifest.save(p)
    return p


def test_env_file_pins_frontend_image_when_manifest_has_one(
    tmp_path: Path, full_stack_manifest: Path
):
    deploy_state = tmp_path / "deploy"
    manifest = ReleaseManifest.load(full_stack_manifest)

    Deployer(manifest_path=full_stack_manifest, state_dir=deploy_state).prepare_environment_file(
        manifest
    )
    deploy_env = (deploy_state / ".env.production").read_text(encoding="utf-8")
    Rollbacker(
        target_manifest=full_stack_manifest, state_dir=deploy_state
    ).prepare_environment_file(manifest)
    rollback_env = (deploy_state / ".env.production").read_text(encoding="utf-8")

    expected = f"FRONTEND_IMAGE_REF=ghcr.io/cuongmotnang/booking-frontend@{DIGEST_WEB}"
    assert expected in deploy_env
    assert expected in rollback_env


def test_env_file_omits_frontend_image_for_backend_only_manifest(tmp_path: Path, v1_manifest: Path):
    deploy_state = tmp_path / "deploy"
    Deployer(manifest_path=v1_manifest, state_dir=deploy_state).prepare_environment_file(
        ReleaseManifest.load(v1_manifest)
    )

    assert "FRONTEND_IMAGE_REF" not in (deploy_state / ".env.production").read_text("utf-8")


def test_deploy_pulls_every_pinned_image(tmp_path: Path, full_stack_manifest: Path):
    deployer = Deployer(manifest_path=full_stack_manifest, state_dir=tmp_path / "deploy")

    with patch.object(deployer, "execute_command") as execute:
        deployer.deploy_containers(ReleaseManifest.load(full_stack_manifest))

    pulled = [c.args[0][2] for c in execute.call_args_list if c.args[0][:2] == ["docker", "pull"]]
    assert pulled == [
        f"ghcr.io/cuongmotnang/booking-backend@{DIGEST_V2}",
        f"ghcr.io/cuongmotnang/booking-frontend@{DIGEST_WEB}",
    ]
