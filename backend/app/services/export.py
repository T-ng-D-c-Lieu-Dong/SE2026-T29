"""Authorisation, scoping and CSV rendering for the appointment export (VT-119)."""

from __future__ import annotations

import csv
import hmac
import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from app.domain import ExportForbidden, ExportUnauthenticated, InvalidExportRange
from app.services.booking import BOOKING_TIMEZONE

ROLE_STAFF = "export_staff"
ROLE_ADMIN = "export_admin"
EXPORT_ROLES = frozenset({ROLE_STAFF, ROLE_ADMIN})
MAX_WINDOW_DAYS = 31
CSV_COLUMNS = ("id", "customer_name", "starts_at", "status", "created_at", "cancelled_at")
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class ExportScope:
    start: datetime
    end: datetime
    include_cancelled: bool


def parse_api_keys(raw: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        token, separator, role = item.rpartition(":")
        if not separator or not token or not role:
            raise ValueError("export API keys must look like token:role")
        keys[token.strip()] = role.strip()
    return keys


def authenticate(api_key: str | None, keys: dict[str, str]) -> str:
    """Return the caller's role; compare in constant time against every configured key."""
    role: str | None = None
    candidate = (api_key or "").encode()
    for token, token_role in keys.items():
        if hmac.compare_digest(candidate, token.encode()) and api_key:
            role = token_role
    if role is None:
        raise ExportUnauthenticated("A valid API key is required")
    return role


def require_export_role(role: str) -> None:
    if role not in EXPORT_ROLES:
        raise ExportForbidden("This role may not export appointments")


def resolve_window(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    if date_to < date_from:
        raise InvalidExportRange("'from' must not be after 'to'")
    if (date_to - date_from).days + 1 > MAX_WINDOW_DAYS:
        raise InvalidExportRange(f"export window must not exceed {MAX_WINDOW_DAYS} days")
    local_start = datetime.combine(date_from, time(0, 0), tzinfo=BOOKING_TIMEZONE)
    local_end = datetime.combine(date_to + timedelta(days=1), time(0, 0), tzinfo=BOOKING_TIMEZONE)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def authorize_scope(role: str, include_cancelled: bool) -> None:
    if include_cancelled and role != ROLE_ADMIN:
        raise ExportForbidden("Only export_admin may include cancelled appointments")


def evaluate_export_request(
    api_key: str | None,
    keys: dict[str, str],
    date_from: date,
    date_to: date,
    include_cancelled: bool,
) -> ExportScope:
    """Decision-table entry point. Precedence: 401 -> 403 -> 422 -> 403 (scope)."""
    role = authenticate(api_key, keys)
    require_export_role(role)
    start, end = resolve_window(date_from, date_to)
    authorize_scope(role, include_cancelled)
    return ExportScope(start, end, include_cancelled)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    text = value.isoformat() if isinstance(value, datetime) else str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def render_csv(appointments: Iterable[Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for item in appointments:
        writer.writerow([_cell(getattr(item, column)) for column in CSV_COLUMNS])
    return buffer.getvalue()
