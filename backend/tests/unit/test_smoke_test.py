from unittest.mock import patch

from scripts.smoke_test import SmokeTestRunner


def test_smoke_runner_readiness_success():
    runner = SmokeTestRunner(base_url="http://mock-service", readiness_timeout_seconds=2.0)
    with patch.object(runner, "_http_request", return_value=(200, {"status": "ok"})):
        res = runner.wait_for_readiness()
        assert res.success
        assert res.step == "readiness_check"
        assert "HTTP 200" in res.message


def test_smoke_runner_readiness_failure():
    runner = SmokeTestRunner(base_url="http://mock-service", readiness_timeout_seconds=0.5)
    with patch.object(runner, "_http_request", return_value=(503, {"status": "database down"})):
        res = runner.wait_for_readiness()
        assert not res.success
        assert "timed out" in res.message


def test_smoke_runner_version_check_success():
    runner = SmokeTestRunner(
        base_url="http://mock-service",
        expected_release="v0.1.0",
        expected_commit_sha="e0426ba69da49d4f2bd56718a0f7a6392d8dcae2",
    )
    mock_resp = {
        "release": "v0.1.0",
        "commit_sha": "e0426ba69da49d4f2bd56718a0f7a6392d8dcae2",
    }
    with patch.object(runner, "_http_request", return_value=(200, mock_resp)):
        res = runner.check_version()
        assert res.success
        assert res.step == "version_check"
        assert "v0.1.0" in res.message


def test_smoke_runner_version_check_mismatch():
    runner = SmokeTestRunner(
        base_url="http://mock-service",
        expected_release="v0.2.0",
        expected_commit_sha="e0426ba69da49d4f2bd56718a0f7a6392d8dcae2",
    )
    mock_resp = {
        "release": "v0.1.0",  # Different release!
        "commit_sha": "e0426ba69da49d4f2bd56718a0f7a6392d8dcae2",
    }
    with patch.object(runner, "_http_request", return_value=(200, mock_resp)):
        res = runner.check_version()
        assert not res.success
        assert "Version mismatch" in res.message


def test_smoke_runner_version_check_rejects_wrong_commit():
    runner = SmokeTestRunner(
        base_url="http://mock-service",
        expected_release="v0.1.0",
        expected_commit_sha="expected-sha",
    )
    with patch.object(
        runner,
        "_http_request",
        return_value=(200, {"release": "v0.1.0", "commit_sha": "wrong-sha"}),
    ) as request:
        result = runner.check_version()

    request.assert_called_once_with("GET", "/api/version")
    assert not result.success
    assert "Commit mismatch" in result.message


def test_smoke_runner_business_flow_success():
    runner = SmokeTestRunner(base_url="http://mock-service")

    responses = [
        (200, [{"starts_at": "2026-10-15T10:00:00+07:00"}]),
        (201, {"id": "11111111-1111-1111-1111-111111111111", "status": "booked"}),
        (204, ""),
    ]

    with patch.object(runner, "_http_request", side_effect=responses):
        res = runner.check_business_flow()
        assert res.success
        assert res.step == "business_flow"
        assert "Business smoke test passed" in res.message


def test_smoke_runner_business_flow_fails_when_booking_fails():
    runner = SmokeTestRunner(base_url="http://mock-service")

    responses = [
        (200, [{"starts_at": "2026-10-15T10:00:00+07:00"}]),
        (409, {"detail": "Slot already booked"}),
    ]

    with patch.object(runner, "_http_request", side_effect=responses):
        res = runner.check_business_flow()
        assert not res.success
        assert "POST /api/appointments failed with status 409" in res.message
