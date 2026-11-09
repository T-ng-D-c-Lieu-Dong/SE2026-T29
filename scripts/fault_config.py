"""Bounded fault settings carried by release manifests (no backend dependencies)."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class FaultConfig:
    mode: str = "off"
    rate: float = 1.0
    until: str | None = None
    latency_seconds: float = 3.0
    duration_seconds: int | None = None

    def validate(self) -> list[str]:
        errors = []
        if self.mode not in ("off", "error", "latency"):
            errors.append("Fault mode must be off, error, or latency.")
        for name, value, maximum in (
            ("rate", self.rate, 1.0),
            ("latency_seconds", self.latency_seconds, 30.0),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= maximum
            ):
                errors.append(f"Fault {name} must be a finite number between 0 and {maximum}.")
        if self.duration_seconds is not None and (
            type(self.duration_seconds) is not int or not 1 <= self.duration_seconds <= 3600
        ):
            errors.append("Fault duration_seconds must be an integer between 1 and 3600.")
        if self.until is not None:
            try:
                expiry = datetime.fromisoformat(self.until)
                if expiry.utcoffset() is None:
                    raise ValueError("Missing timezone")
            except (TypeError, ValueError):
                errors.append("Fault until must be an ISO timestamp with a UTC offset.")
        elif self.mode != "off" and self.duration_seconds is None:
            errors.append("Active fault requires until or bounded duration_seconds.")
        return errors

    def activate(self, now: datetime | None = None) -> FaultConfig:
        if errors := self.validate():
            raise ValueError("; ".join(errors))
        if self.mode == "off" or self.until is not None:
            return self
        assert self.duration_seconds is not None
        now = now or datetime.now(UTC)
        return replace(self, until=(now + timedelta(seconds=self.duration_seconds)).isoformat())

    def is_active(self, now: datetime | None = None) -> bool:
        return (
            self.mode != "off"
            and self.rate > 0
            and self.until is not None
            and datetime.fromisoformat(self.until) > (now or datetime.now(UTC))
        )

    def to_environment(self) -> dict[str, str]:
        if errors := self.validate():
            raise ValueError("; ".join(errors))
        if self.mode != "off" and self.until is None:
            raise ValueError("Fault expiry must be activated and recorded before rollback.")
        return {
            "BOOKING_FAULT_MODE": self.mode,
            "BOOKING_FAULT_RATE": str(self.rate),
            "BOOKING_FAULT_UNTIL": datetime.fromisoformat(self.until).isoformat()
            if self.until
            else "",
            "BOOKING_FAULT_LATENCY_SECONDS": str(self.latency_seconds),
        }
