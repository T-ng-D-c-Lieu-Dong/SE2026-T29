"""Unit tests for booking integrity checker (TASK-007 / C136)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
import urllib.error

from scripts.booking_integrity import (
    BookingRecord,
    IntegritySnapshot,
    fetch_bookings,
    verify_integrity,
)

T0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)


def test_booking_record_matching():
    r1 = BookingRecord(
        id="1", customer_name="Alice", starts_at="2026-11-03T10:00:00", status="CONFIRMED"
    )
    r2 = BookingRecord(
        id="1", customer_name="Alice", starts_at="2026-11-03T10:00:00", status="CONFIRMED"
    )
    r3 = BookingRecord(
        id="1", customer_name="Alice", starts_at="2026-11-03T10:00:00", status="CANCELLED"
    )

    assert r1.matches(r2) is True
    assert r1.matches(r3) is False


def test_integrity_snapshot_persistence(tmp_path):
    target = tmp_path / "snapshot.json"
    snapshot = IntegritySnapshot(
        captured_at=T0.isoformat(),
        base_url="http://localhost:8000",
        count=2,
        bookings={
            "b-1": {
                "id": "b-1",
                "customer_name": "Bob",
                "starts_at": "2026-11-03T09:00:00",
                "status": "CONFIRMED",
            },
            "b-2": {
                "id": "b-2",
                "customer_name": "Carol",
                "starts_at": "2026-11-03T10:00:00",
                "status": "CONFIRMED",
            },
        },
    )
    snapshot.save(target)
    assert target.is_file()

    loaded = IntegritySnapshot.load(target)
    assert loaded.count == 2
    assert "b-1" in loaded.bookings
    assert loaded.bookings["b-1"]["customer_name"] == "Bob"


def test_verify_integrity_all_intact():
    baseline = IntegritySnapshot(
        captured_at=T0.isoformat(),
        base_url="http://localhost:8000",
        count=2,
        bookings={
            "b-1": {
                "id": "b-1",
                "customer_name": "Bob",
                "starts_at": "2026-11-03T09:00:00",
                "status": "CONFIRMED",
            },
            "b-2": {
                "id": "b-2",
                "customer_name": "Carol",
                "starts_at": "2026-11-03T10:00:00",
                "status": "CONFIRMED",
            },
        },
    )
    current = [
        BookingRecord(
            id="b-1", customer_name="Bob", starts_at="2026-11-03T09:00:00", status="CONFIRMED"
        ),
        BookingRecord(
            id="b-2", customer_name="Carol", starts_at="2026-11-03T10:00:00", status="CONFIRMED"
        ),
        BookingRecord(
            id="b-3", customer_name="New Guy", starts_at="2026-11-03T11:00:00", status="CONFIRMED"
        ),
    ]
    report = verify_integrity(baseline, current, now=T0)
    assert report.is_valid is True
    assert report.baseline_count == 2
    assert report.current_count == 3
    assert report.intact_count == 2
    assert len(report.missing_ids) == 0
    assert len(report.corrupted_ids) == 0
    assert report.new_ids == ["b-3"]


def test_verify_integrity_missing_booking():
    baseline = IntegritySnapshot(
        captured_at=T0.isoformat(),
        base_url="http://localhost:8000",
        count=2,
        bookings={
            "b-1": {
                "id": "b-1",
                "customer_name": "Bob",
                "starts_at": "2026-11-03T09:00:00",
                "status": "CONFIRMED",
            },
            "b-2": {
                "id": "b-2",
                "customer_name": "Carol",
                "starts_at": "2026-11-03T10:00:00",
                "status": "CONFIRMED",
            },
        },
    )
    current = [
        BookingRecord(
            id="b-1", customer_name="Bob", starts_at="2026-11-03T09:00:00", status="CONFIRMED"
        ),
    ]
    report = verify_integrity(baseline, current, now=T0)
    assert report.is_valid is False
    assert report.intact_count == 1
    assert report.missing_ids == ["b-2"]


def test_verify_integrity_corrupted_booking():
    baseline = IntegritySnapshot(
        captured_at=T0.isoformat(),
        base_url="http://localhost:8000",
        count=1,
        bookings={
            "b-1": {
                "id": "b-1",
                "customer_name": "Bob",
                "starts_at": "2026-11-03T09:00:00",
                "status": "CONFIRMED",
            },
        },
    )
    current = [
        BookingRecord(
            id="b-1", customer_name="Bob", starts_at="2026-11-03T09:00:00", status="CANCELLED"
        ),
    ]
    report = verify_integrity(baseline, current, now=T0)
    assert report.is_valid is False
    assert report.intact_count == 0
    assert "b-1" in report.corrupted_ids
    assert report.corrupted_ids["b-1"]["expected"]["status"] == "CONFIRMED"
    assert report.corrupted_ids["b-1"]["actual"]["status"] == "CANCELLED"


def test_fetch_bookings_retry_on_network_glitch():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = (
        b'[{"id":"b-1","customer_name":"Bob","starts_at":"2026-11-03T09:00:00","status":"CONFIRMED"}]'
    )
    mock_resp.__enter__.return_value = mock_resp

    with patch(
        "urllib.request.urlopen",
        side_effect=[urllib.error.URLError("Connection reset"), mock_resp],
    ) as mock_urlopen:
        records = fetch_bookings("http://localhost:8000", max_retries=2, retry_delay=0.01)
        assert len(records) == 1
        assert records[0].id == "b-1"
        assert mock_urlopen.call_count == 2

