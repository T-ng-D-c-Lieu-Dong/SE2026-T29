"""Probe clients must satisfy the private booking API identity contract."""

import io
import json
from email.message import Message
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest
from scripts.persistence_check import PersistenceCheck
from scripts.smoke_test import SmokeTestRunner


class Response(io.BytesIO):
    def __init__(self, status=200, payload=None):
        super().__init__(json.dumps(payload if payload is not None else {}).encode())
        self.status = status


@pytest.fixture
def requests_sent(monkeypatch):
    sent = []

    def send(request, timeout):
        sent.append(request)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", send)
    return sent


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/appointments"),
        ("DELETE", "/api/appointments/booking-id"),
        ("GET", "/api/appointments?limit=100&offset=0"),
        ("GET", "/api/appointments/trash"),
    ],
)
def test_private_probe_requests_send_configured_identity(monkeypatch, requests_sent, method, path):
    monkeypatch.setenv("BOOKING_PROBE_USER_ID", "ci-probe")
    runner = SmokeTestRunner(base_url="http://probe-api")
    runner._http_request(method, path)
    assert requests_sent[0].get_header("X-user-id") == "ci-probe"


@pytest.mark.parametrize("path", ["/health/ready", "/api/version", "/api/slots?date=2030-01-01"])
def test_public_probe_requests_do_not_send_identity(monkeypatch, requests_sent, path):
    monkeypatch.setenv("BOOKING_PROBE_USER_ID", "ci-probe")
    SmokeTestRunner(base_url="http://probe-api")._http_request("GET", path)
    assert requests_sent[0].get_header("X-user-id") is None


def test_explicit_probe_identity_overrides_environment(monkeypatch, requests_sent):
    monkeypatch.setenv("BOOKING_PROBE_USER_ID", "environment-user")
    SmokeTestRunner(base_url="http://probe-api", user_id="explicit-user")._http_request(
        "GET", "/api/appointments"
    )
    assert requests_sent[0].get_header("X-user-id") == "explicit-user"


def test_unconfigured_probe_does_not_invent_identity(monkeypatch, requests_sent):
    monkeypatch.delenv("BOOKING_PROBE_USER_ID", raising=False)
    SmokeTestRunner(base_url="http://probe-api")._http_request("GET", "/api/appointments")
    assert requests_sent[0].get_header("X-user-id") is None


def test_persistence_seed_and_verify_use_same_configured_identity(monkeypatch):
    monkeypatch.setenv("BOOKING_PROBE_USER_ID", "ci-persistence")
    sent = []

    def send(request, timeout):
        sent.append(request)
        path = urlsplit(request.full_url).path
        if path == "/api/slots":
            return Response(payload=[{"starts_at": "2030-01-01T10:00:00+07:00"}])
        if request.get_method() == "POST":
            return Response(201, {"id": "probe-booking", "status": "booked"})
        return Response(
            payload={"items": [{"id": "probe-booking", "status": "booked"}], "total": 1}
        )

    monkeypatch.setattr("urllib.request.urlopen", send)
    check = PersistenceCheck(base_url="http://probe-api")
    seeded = check.seed()
    assert seeded.success
    assert check.verify(seeded.details["id"]).success
    private = [r for r in sent if urlsplit(r.full_url).path == "/api/appointments"]
    assert len(private) == 2
    assert [r.get_header("X-user-id") for r in private] == ["ci-persistence", "ci-persistence"]


def test_probe_still_fails_on_unauthorized_booking(monkeypatch):
    def send(request, timeout):
        if urlsplit(request.full_url).path == "/api/slots":
            return Response(payload=[{"starts_at": "2030-01-01T10:00:00+07:00"}])
        raise HTTPError(request.full_url, 401, "Unauthorized", Message(), io.BytesIO(b"{}"))

    monkeypatch.setattr("urllib.request.urlopen", send)
    result = SmokeTestRunner(base_url="http://probe-api").check_business_flow()
    assert result.success is False
    assert result.step == "business_flow_create"
    assert result.details["status"] == 401
