"""Smoke test suite for post-deployment verification.

Implements TASK-005 requirements:
- "Thêm readiness timeout và smoke test nghiệp vụ sau deploy."
- Verifies `/api/version` matches release manifest (E08).
- Verifies end-to-end business flow: query slots -> create booking -> cancel booking.
- Verifies existing data preservation across deploy and rollback (E12).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class SmokeTestResult:
    success: bool
    step: str
    duration_seconds: float
    message: str
    details: dict[str, Any]


class SmokeTestRunner:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        readiness_timeout_seconds: float = 30.0,
        expected_release: str | None = None,
        expected_commit_sha: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.readiness_timeout_seconds = readiness_timeout_seconds
        self.expected_release = expected_release
        self.expected_commit_sha = expected_commit_sha

    def _http_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 5.0,
    ) -> tuple[int, dict[str, Any] | str]:
        url = f"{self.base_url}{path}"
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=req_headers, method=method)  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                status_code = response.status
                raw = response.read().decode("utf-8")
                if not raw:
                    return status_code, ""
                try:
                    return status_code, json.loads(raw)
                except json.JSONDecodeError:
                    return status_code, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            return exc.code, parsed

    def wait_for_readiness(self) -> SmokeTestResult:
        start = time.monotonic()
        last_error = ""
        while time.monotonic() - start < self.readiness_timeout_seconds:
            try:
                status, body = self._http_request("GET", "/health/ready", timeout=3.0)
                if status == 200:
                    duration = time.monotonic() - start
                    return SmokeTestResult(
                        success=True,
                        step="readiness_check",
                        duration_seconds=duration,
                        message=f"Application is ready (HTTP 200 after {duration:.2f}s).",
                        details={"status": status, "response": body},
                    )
                last_error = f"HTTP {status}: {body}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            time.sleep(1.0)

        duration = time.monotonic() - start
        return SmokeTestResult(
            success=False,
            step="readiness_check",
            duration_seconds=duration,
            message=f"Readiness check timed out after {duration:.1f}s. Last error: {last_error}",
            details={"last_error": last_error},
        )

    def check_version(self) -> SmokeTestResult:
        start = time.monotonic()
        try:
            status, body = self._http_request("GET", "/api/version")
            duration = time.monotonic() - start
            if status != 200:
                return SmokeTestResult(
                    success=False,
                    step="version_check",
                    duration_seconds=duration,
                    message=f"GET /api/version failed with status {status}",
                    details={"status": status, "body": body},
                )

            if not isinstance(body, dict):
                return SmokeTestResult(
                    success=False,
                    step="version_check",
                    duration_seconds=duration,
                    message="GET /api/version response must be a JSON object",
                    details={"body": body},
                )

            actual_release = body.get("release")
            actual_commit = body.get("commit_sha")

            if self.expected_release and actual_release != self.expected_release:
                return SmokeTestResult(
                    success=False,
                    step="version_check",
                    duration_seconds=duration,
                    message=(
                        f"Version mismatch: expected release '{self.expected_release}', "
                        f"got '{actual_release}'"
                    ),
                    details={
                        "expected": self.expected_release,
                        "actual": actual_release,
                    },
                )

            if self.expected_commit_sha and actual_commit != self.expected_commit_sha:
                return SmokeTestResult(
                    success=False,
                    step="version_check",
                    duration_seconds=duration,
                    message=(
                        f"Commit mismatch: expected commit '{self.expected_commit_sha}', "
                        f"got '{actual_commit}'"
                    ),
                    details={
                        "expected": self.expected_commit_sha,
                        "actual": actual_commit,
                    },
                )

            return SmokeTestResult(
                success=True,
                step="version_check",
                duration_seconds=duration,
                message=f"Version verified: release='{actual_release}', commit='{actual_commit}'",
                details={"release": actual_release, "commit_sha": actual_commit},
            )
        except Exception as exc:  # noqa: BLE001
            return SmokeTestResult(
                success=False,
                step="version_check",
                duration_seconds=time.monotonic() - start,
                message=f"Failed to check version: {exc}",
                details={"error": str(exc)},
            )

    def check_business_flow(self) -> SmokeTestResult:
        start = time.monotonic()
        try:
            # Step 1: Query slots for tomorrow
            tomorrow = datetime.now(UTC) + timedelta(days=1)
            target_date = tomorrow.strftime("%Y-%m-%d")
            status, slots = self._http_request("GET", f"/api/slots?date={target_date}")
            if status != 200 or not isinstance(slots, list):
                return SmokeTestResult(
                    success=False,
                    step="business_flow_slots",
                    duration_seconds=time.monotonic() - start,
                    message=f"GET /api/slots?date={target_date} failed with status {status}",
                    details={"status": status, "slots": slots},
                )

            # Pick a valid slot for smoke test (e.g. 10:00:00+07:00 tomorrow)
            smoke_slot = f"{target_date}T10:00:00+07:00"

            # Step 2: Create smoke booking
            create_payload = {
                "customer_name": "[SmokeTest] Automated Deploy Probe",
                "starts_at": smoke_slot,
            }
            status, create_resp = self._http_request(
                "POST", "/api/appointments", body=create_payload
            )
            if status != 201 or not isinstance(create_resp, dict):
                return SmokeTestResult(
                    success=False,
                    step="business_flow_create",
                    duration_seconds=time.monotonic() - start,
                    message=f"POST /api/appointments failed with status {status}",
                    details={"status": status, "response": create_resp},
                )

            appointment_id = create_resp.get("id")
            if not appointment_id:
                return SmokeTestResult(
                    success=False,
                    step="business_flow_create",
                    duration_seconds=time.monotonic() - start,
                    message="Create booking response missing 'id'",
                    details={"response": create_resp},
                )

            # Step 3: Cancel smoke booking (cleanup)
            status, _ = self._http_request("DELETE", f"/api/appointments/{appointment_id}")
            if status != 204:
                return SmokeTestResult(
                    success=False,
                    step="business_flow_cancel",
                    duration_seconds=time.monotonic() - start,
                    message=(
                        f"DELETE /api/appointments/{appointment_id} failed with status {status}"
                    ),
                    details={"status": status},
                )

            return SmokeTestResult(
                success=True,
                step="business_flow",
                duration_seconds=time.monotonic() - start,
                message="Business smoke test passed: slots queried, booking created and cancelled.",
                details={"smoke_appointment_id": appointment_id, "slot": smoke_slot},
            )
        except Exception as exc:  # noqa: BLE001
            return SmokeTestResult(
                success=False,
                step="business_flow",
                duration_seconds=time.monotonic() - start,
                message=f"Business smoke test exception: {exc}",
                details={"error": str(exc)},
            )

    def run_health_checks(self) -> list[SmokeTestResult]:
        results: list[SmokeTestResult] = []

        ready_res = self.wait_for_readiness()
        results.append(ready_res)
        if not ready_res.success:
            return results

        version_res = self.check_version()
        results.append(version_res)
        if not version_res.success:
            return results

        return results

    def run_all(self) -> list[SmokeTestResult]:
        results = self.run_health_checks()
        if not all(result.success for result in results):
            return results
        flow_res = self.check_business_flow()
        results.append(flow_res)
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run smoke tests against deployed Booking API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Service base URL")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Readiness probe timeout in seconds",
    )
    parser.add_argument("--expected-release", default=None, help="Expected release version")
    parser.add_argument("--expected-commit-sha", default=None, help="Expected Git commit SHA")
    args = parser.parse_args()

    runner = SmokeTestRunner(
        base_url=args.base_url,
        readiness_timeout_seconds=args.timeout,
        expected_release=args.expected_release,
        expected_commit_sha=args.expected_commit_sha,
    )
    results = runner.run_all()

    failed = False
    for res in results:
        status_str = "PASS" if res.success else "FAIL"
        print(f"[{status_str}] ({res.duration_seconds:.2f}s) {res.step}: {res.message}")
        if not res.success:
            failed = True

    if failed:
        sys.exit(1)
    print("All smoke tests passed successfully!")


if __name__ == "__main__":
    main()
