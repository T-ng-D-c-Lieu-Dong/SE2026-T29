"""Audit a paired performance JSON/text artifact against its raw task samples."""

import json
import math
import sys
from pathlib import Path

from scripts.loadtest_vt116 import calculate_percentile

path = Path(sys.argv[1])
result = json.loads(path.read_text())
log = path.with_suffix(".log").read_text()
samples = result["samples"]
latencies = [sample["latency_seconds"] for sample in samples if sample["success"]]
assert len(samples) == result["total_lifecycle_tasks"] == 200
assert len(latencies) == result["completed_tasks"] == 200
assert result["error_count"] == 0
assert result["measured_request_count"] == 600
assert result["peak_lifecycle_inflight"] == result["peak_http_inflight"] == 40
assert result["concurrency_cap"] == 40
assert result["run_id"] in log and result["tested_commit"] in log
for percentile in (50, 95, 99):
    measured = calculate_percentile(latencies, percentile)
    assert math.isclose(measured, result["latency_stats_seconds"][f"p{percentile}"])
    assert f"{measured * 1000:.2f} ms" in log
assert min(latencies) == result["latency_stats_seconds"]["min"]
assert max(latencies) == result["latency_stats_seconds"]["max"]
print(f"PASS paired run {result['run_id']}: 200 samples, 600 requests, peak 40, metrics agree")
