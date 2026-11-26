"""Capture read-only Prometheus evidence; never infer drill success from readiness."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def capture(base_url: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    checks = {}
    errors = {}
    endpoints = {
        "targets": "/api/v1/targets",
        "rules": "/api/v1/rules",
        "probe": "/api/v1/query?"
        + urllib.parse.urlencode({"query": 'probe_success{job="booking-api-readiness"}'}),
        "http_metrics": "/api/v1/query?"
        + urllib.parse.urlencode(
            {"query": 'http_server_duration_milliseconds_count{service_name="booking-api"}'}
        ),
    }
    for name, endpoint in endpoints.items():
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=10) as response:
                payload = json.load(response)
            if payload.get("status") != "success":
                raise ValueError("Prometheus did not return success")
            (output / f"{name}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if name == "targets":
                targets = payload["data"]["activeTargets"]
                expected = {
                    "otel-collector",
                    "booking-api-readiness",
                    "blackbox-exporter",
                    "node-exporter",
                    "cadvisor",
                    "prometheus",
                }
                healthy = {t["labels"].get("job") for t in targets if t["health"] == "up"}
                checks[name] = expected <= healthy and all(t["health"] == "up" for t in targets)
            elif name == "rules":
                rules = [r for g in payload["data"]["groups"] for r in g["rules"]]
                expected = {"HighErrorRate": 120, "ApiProbeDown": 60, "HighLatencyP95": 300}
                checks[name] = all(
                    any(
                        r["name"] == alert
                        and r.get("duration") == duration
                        and r.get("health") == "ok"
                        and not r.get("lastError")
                        for r in rules
                    )
                    for alert, duration in expected.items()
                )
            elif name == "probe":
                results = payload["data"]["result"]
                checks[name] = bool(results) and all(float(r["value"][1]) == 1 for r in results)
            else:
                results = payload["data"]["result"]
                forbidden = {"trace_id", "span_id", "appointment_id", "customer_name"}
                checks[name] = bool(results) and all(
                    not forbidden.intersection(r["metric"]) for r in results
                )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks[name] = False
            errors[name] = str(exc)
    summary = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "prometheus_url": base_url,
        "checks": checks,
        "errors": errors,
        "success": all(checks.values()),
        "scope": "Read-only snapshot; does not prove error correlation, outage or delivery. "
        "HTTP check only rejects known forbidden label names; review other labels manually.",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument(
        "--output", type=Path, required=True, help="Use a separate directory for each capture."
    )
    args = parser.parse_args()
    summary = capture(args.prometheus_url, args.output)
    print(json.dumps(summary, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
