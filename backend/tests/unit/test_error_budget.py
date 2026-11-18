"""Unit tests for error budget and burn rate calculator (TASK-007 Hardening)."""

import pytest
from scripts.calculate_error_budget import ErrorBudgetCalculator


def test_zero_requests_returns_ok():
    calc = ErrorBudgetCalculator(slo_target=0.99)
    res = calc.calculate(total_requests=0, error_requests=0)
    assert res.status == "OK"
    assert res.burn_rate == 0.0
    assert res.is_violating is False


def test_normal_traffic_within_budget():
    calc = ErrorBudgetCalculator(slo_target=0.99)
    # 0.5% error rate -> burn rate 0.5x
    res = calc.calculate(total_requests=1000, error_requests=5)
    assert res.status == "OK"
    assert res.burn_rate == 0.5
    assert res.is_violating is False


def test_warning_burn_rate_threshold():
    calc = ErrorBudgetCalculator(slo_target=0.99)
    # 6% error rate with allowed 1% -> 6.0x burn rate
    res = calc.calculate(total_requests=1000, error_requests=60, window_hours=6.0)
    assert res.status == "WARNING"
    assert res.burn_rate == 6.0
    assert res.is_violating is True


def test_critical_burn_rate_threshold():
    calc = ErrorBudgetCalculator(slo_target=0.99)
    # 15% error rate with allowed 1% -> 15.0x burn rate (>= 14.4x)
    res = calc.calculate(total_requests=1000, error_requests=150, window_hours=1.0)
    assert res.status == "CRITICAL"
    assert res.burn_rate == 15.0
    assert res.is_violating is True


def test_invalid_parameters():
    with pytest.raises(ValueError, match="SLO target must be between 0 and 1"):
        ErrorBudgetCalculator(slo_target=1.5)

    calc = ErrorBudgetCalculator(slo_target=0.99)
    with pytest.raises(ValueError, match="Requests cannot be negative"):
        calc.calculate(total_requests=-1, error_requests=0)

    with pytest.raises(ValueError, match="Error requests cannot exceed total requests"):
        calc.calculate(total_requests=100, error_requests=105)
