"""Unit tests for unified SRE operational CLI (TASK-005 / TASK-007 Hardening)."""

from pathlib import Path

from scripts.release_manifest import ReleaseManifest
from scripts.sre_cli import build_parser, cmd_budget, cmd_status


def test_sre_cli_parser_commands():
    parser = build_parser()

    args_status = parser.parse_args(["status"])
    assert args_status.command == "status"

    args_budget = parser.parse_args(["budget", "--total", "1000", "--errors", "5"])
    assert args_budget.command == "budget"
    assert args_budget.total == 1000
    assert args_budget.errors == 5

    args_rollback = parser.parse_args(["rollback", "--dry-run"])
    assert args_rollback.command == "rollback"
    assert args_rollback.dry_run is True


def test_cmd_status_with_manifest(tmp_path: Path, capsys):
    state_dir = tmp_path
    manifest_path = state_dir / "current-manifest.json"
    manifest = ReleaseManifest.load(Path("docs/releases/v0.2.1.json"))
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["--state-dir", str(state_dir), "status"])
    code = cmd_status(args)

    assert code == 0
    out = capsys.readouterr().out
    assert "Active Release:     v0.2.1" in out
    assert "Deployment Lock:    UNLOCKED" in out


def test_cmd_budget_nominal_and_violation(capsys):
    parser = build_parser()

    # OK scenario
    args_ok = parser.parse_args(["budget", "--total", "1000", "--errors", "2"])
    code_ok = cmd_budget(args_ok)
    assert code_ok == 0
    out_ok = capsys.readouterr().out
    assert "Status: [OK]" in out_ok

    # Critical scenario
    args_crit = parser.parse_args(["budget", "--total", "1000", "--errors", "150"])
    code_crit = cmd_budget(args_crit)
    assert code_crit == 1
    out_crit = capsys.readouterr().out
    assert "Status: [CRITICAL]" in out_crit
