"""The performance verdict must never pass an empty or failed workload."""

import pytest

from scripts.loadtest_vt116 import calculate_percentile, performance_goal_met


def test_percentile_uses_interpolated_sample_rank():
    assert calculate_percentile([4.0, 1.0, 2.0, 3.0], 50) == 2.5
    assert calculate_percentile([4.0, 1.0, 2.0, 3.0], 95) == pytest.approx(3.85)


def test_empty_workload_cannot_meet_performance_goal():
    assert performance_goal_met([], error_count=200, total_tasks=200) is False


def test_partial_workload_cannot_meet_performance_goal():
    assert performance_goal_met([0.1] * 199, error_count=1, total_tasks=200) is False


def test_slow_workload_fails_performance_goal():
    assert performance_goal_met([1.6] * 200, error_count=0, total_tasks=200) is False


def test_completed_fast_workload_meets_performance_goal():
    assert performance_goal_met([0.6] * 200, error_count=0, total_tasks=200) is True
