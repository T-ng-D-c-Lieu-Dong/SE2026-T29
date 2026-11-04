"""Unit tests for repository_dispatch automated rollback trigger (TASK-007 / C187)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
import urllib.error

import pytest
from scripts.trigger_rollback_dispatch import (
    DEFAULT_EVENT_TYPE,
    build_dispatch_payload,
    main,
    send_rollback_dispatch,
)

T0 = datetime(2026, 11, 2, 15, 0, 0, tzinfo=UTC)


def test_build_dispatch_payload():
    payload = build_dispatch_payload(
        alert_name="BookingHighHttpErrorRate",
        reason="Error rate spiked above 5%",
        target_manifest="/opt/booking/state/v0.2.0.json",
        severity="critical",
        source="alertmanager",
        now=T0,
    )
    assert payload["event_type"] == DEFAULT_EVENT_TYPE
    client_payload = payload["client_payload"]
    assert client_payload["alert_name"] == "BookingHighHttpErrorRate"
    assert client_payload["reason"] == "Error rate spiked above 5%"
    assert client_payload["target_manifest"] == "/opt/booking/state/v0.2.0.json"
    assert client_payload["severity"] == "critical"
    assert client_payload["source"] == "alertmanager"
    assert client_payload["triggered_at"] == T0.isoformat()


def test_send_rollback_dispatch_dry_run(capsys):
    payload = build_dispatch_payload(now=T0)
    res = send_rollback_dispatch(
        repo="T-ng-D-c-Lieu-Dong/SE2026-T29",
        token="fake-token",
        payload=payload,
        dry_run=True,
    )
    assert res["status"] == "dry-run"
    assert "https://api.github.com/repos/T-ng-D-c-Lieu-Dong/SE2026-T29/dispatches" in res["url"]
    out = capsys.readouterr().out
    assert "[DRY-RUN]" in out
    assert "BookingHighHttpErrorRate" in out


def test_send_rollback_dispatch_success():
    payload = build_dispatch_payload(now=T0)
    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = send_rollback_dispatch(
            repo="owner/repo",
            token="ghp_test12345",
            payload=payload,
            dry_run=False,
        )
        assert res["status"] == "success"
        assert res["status_code"] == 204
        assert mock_urlopen.call_count == 1
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.headers["Authorization"] == "Bearer ghp_test12345"


def test_send_rollback_dispatch_http_error():
    payload = build_dispatch_payload(now=T0)
    mock_err = urllib.error.HTTPError(
        url="https://api.github.com",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=MagicMock(read=lambda: b'{"message": "Bad credentials"}'),
    )

    with patch("urllib.request.urlopen", side_effect=mock_err):
        with pytest.raises(RuntimeError, match="HTTP 401.*Bad credentials"):
            send_rollback_dispatch(
                repo="owner/repo",
                token="invalid-token",
                payload=payload,
                dry_run=False,
            )


def test_cli_dry_run_flow(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "trigger_rollback_dispatch.py",
            "--repo",
            "owner/repo",
            "--dry-run",
            "--reason",
            "Test drill trigger",
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "[DRY-RUN]" in out
    assert "[SUCCESS] Rollback dispatch triggered: dry-run" in out
