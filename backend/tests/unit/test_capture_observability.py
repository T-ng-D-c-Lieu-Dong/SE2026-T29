import io
import json
from unittest.mock import patch

import pytest
from scripts.capture_observability import capture


def test_empty_prometheus_data_cannot_pass(tmp_path):
    responses = [
        {"activeTargets": []},
        {"groups": []},
        {"result": []},
        {"result": []},
    ]
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            io.BytesIO(json.dumps({"status": "success", "data": data}).encode())
            for data in responses
        ],
    ):
        result = capture("http://localhost:9090", tmp_path)
    assert not result["success"]
    assert not any(result["checks"].values())


def test_connection_failure_is_saved_without_aborting_other_checks(tmp_path):
    with patch("urllib.request.urlopen", side_effect=OSError("unavailable")) as request:
        result = capture("http://localhost:9090", tmp_path)
    assert request.call_count == 4
    assert not result["success"]
    assert len(result["errors"]) == 4
    assert json.loads((tmp_path / "summary.json").read_text())["success"] is False


def test_customer_label_fails_http_metric_check(tmp_path):
    payload = {
        "status": "success",
        "data": {
            "activeTargets": [],
            "groups": [],
            "result": [{"metric": {"customer_name": "private"}, "value": [1, "1"]}],
        },
    }
    with patch(
        "urllib.request.urlopen",
        side_effect=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()),
    ):
        result = capture("http://localhost:9090", tmp_path)
    assert result["checks"]["http_metrics"] is False


@pytest.mark.parametrize(
    "duration,health,expected",
    [
        (120, "ok", True),
        (30, "ok", False),
        (120, "err", False),
    ],
)
def test_rule_requires_current_hold_duration_and_healthy_evaluation(
    tmp_path, duration, health, expected
):
    payload = {
        "status": "success",
        "data": {
            "activeTargets": [],
            "result": [],
            "groups": [
                {
                    "rules": [
                        {"name": "HighErrorRate", "duration": duration, "health": health},
                        {"name": "ApiProbeDown", "duration": 60, "health": "ok"},
                        {"name": "HighLatencyP95", "duration": 300, "health": "ok"},
                    ]
                }
            ],
        },
    }
    with patch(
        "urllib.request.urlopen",
        side_effect=lambda *a, **k: io.BytesIO(json.dumps(payload).encode()),
    ):
        result = capture("http://localhost:9090", tmp_path)
    assert result["checks"]["rules"] is expected
