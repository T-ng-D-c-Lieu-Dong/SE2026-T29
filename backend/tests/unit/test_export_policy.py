"""VT-119 unit tests: decision table for the appointment export policy.

Conditions: C1 key valid, C2 role may export, C3 window valid, C4 asks cancelled,
C5 role is admin. Evaluation precedence: C1 -> C2 -> C3 -> (C4 and C5).

R1: C1=N                          -> 401
R2: C1=Y C2=N                     -> 403
R3: C1=Y C2=Y C3=N                -> 422
R4: C1=Y C2=Y C3=Y C4=N           -> 200 booked only
R5: C1=Y C2=Y C3=Y C4=Y C5=Y      -> 200 including cancelled
R6: C1=Y C2=Y C3=Y C4=Y C5=N      -> 403 (no silent downgrade)
"""

import csv
import io
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.domain import ExportForbidden, ExportUnauthenticated, InvalidExportRange
from app.services.export import (
    CSV_COLUMNS,
    evaluate_export_request,
    parse_api_keys,
    render_csv,
    resolve_window,
)

KEYS = parse_api_keys("k-admin:export_admin,k-staff:export_staff,k-viewer:viewer")
OK_FROM, OK_TO = date(2026, 11, 10), date(2026, 11, 12)


@pytest.mark.parametrize(
    ("rule", "api_key", "date_from", "date_to", "include_cancelled", "expected"),
    [
        ("R1-no-key", None, OK_FROM, OK_TO, False, ExportUnauthenticated),
        ("R1-wrong-key", "nope", OK_FROM, OK_TO, False, ExportUnauthenticated),
        ("R1-precedence-over-R3", None, OK_TO, OK_FROM, False, ExportUnauthenticated),
        ("R2-viewer", "k-viewer", OK_FROM, OK_TO, False, ExportForbidden),
        ("R2-precedence-over-R3", "k-viewer", OK_TO, OK_FROM, False, ExportForbidden),
        ("R3-from-after-to", "k-staff", OK_TO, OK_FROM, False, InvalidExportRange),
        (
            "R3-window-32-days",
            "k-staff",
            date(2026, 11, 1),
            date(2026, 12, 2),
            False,
            InvalidExportRange,
        ),
        ("R4-staff", "k-staff", OK_FROM, OK_TO, False, False),
        ("R4-admin", "k-admin", OK_FROM, OK_TO, False, False),
        ("R4-boundary-31-days", "k-staff", date(2026, 11, 1), date(2026, 12, 1), False, False),
        ("R5-admin-cancelled", "k-admin", OK_FROM, OK_TO, True, True),
        ("R6-staff-cancelled", "k-staff", OK_FROM, OK_TO, True, ExportForbidden),
    ],
    ids=lambda v: v if isinstance(v, str) and v.startswith("R") else None,
)
def test_export_decision_table(rule, api_key, date_from, date_to, include_cancelled, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            evaluate_export_request(api_key, KEYS, date_from, date_to, include_cancelled)
        return
    scope = evaluate_export_request(api_key, KEYS, date_from, date_to, include_cancelled)
    assert scope.include_cancelled is expected


def test_window_is_local_calendar_days_converted_to_utc_half_open() -> None:
    start, end = resolve_window(date(2026, 11, 10), date(2026, 11, 10))

    assert start == datetime(2026, 11, 9, 17, 0, tzinfo=UTC)
    assert end == datetime(2026, 11, 10, 17, 0, tzinfo=UTC)


def test_parse_api_keys_ignores_blank_and_rejects_malformed() -> None:
    assert parse_api_keys("") == {}
    assert parse_api_keys(" a:export_staff , ,b:viewer ") == {"a": "export_staff", "b": "viewer"}
    with pytest.raises(ValueError):
        parse_api_keys("missing-role")


def _row(**overrides):
    base = {
        "id": "00000000-0000-0000-0000-000000000001",
        "customer_name": "Lan",
        "starts_at": datetime(2026, 11, 10, 3, 0, tzinfo=UTC),
        "status": "booked",
        "created_at": datetime(2026, 11, 1, 3, 0, tzinfo=UTC),
        "cancelled_at": None,
    }
    return SimpleNamespace(**{**base, **overrides})


def test_render_csv_header_and_empty_result() -> None:
    parsed = list(csv.reader(io.StringIO(render_csv([]))))

    assert parsed == [list(CSV_COLUMNS)]


@pytest.mark.parametrize("payload", ["=1+1", "+cmd", "-2", "@SUM(A1)", "\tTAB", "\rCR"])
def test_render_csv_neutralises_formula_injection(payload: str) -> None:
    parsed = list(csv.reader(io.StringIO(render_csv([_row(customer_name=payload)]))))

    assert parsed[1][1].startswith("'")
    assert parsed[1][1][1:] == payload


def test_render_csv_round_trips_commas_quotes_and_newlines() -> None:
    name = 'Nguyen, "Van"\nCuong'
    parsed = list(csv.reader(io.StringIO(render_csv([_row(customer_name=name)]))))

    assert parsed[1][1] == name
