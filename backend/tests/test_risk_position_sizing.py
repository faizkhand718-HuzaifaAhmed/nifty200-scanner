import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_management.position_sizing import compute_position_size, compute_risk_reward  # noqa: E402


def test_compute_position_size_hand_computed():
    # max_risk=1000, entry=100, stop=95 -> stop_distance=5 -> qty=200
    assert compute_position_size(1000.0, 100.0, 95.0) == 200


def test_compute_position_size_rounds_down():
    # max_risk=1000, stop_distance=3 -> 333.33 -> 333
    assert compute_position_size(1000.0, 100.0, 97.0) == 333


def test_compute_position_size_none_when_zero_stop_distance():
    assert compute_position_size(1000.0, 100.0, 100.0) is None


def test_compute_position_size_none_when_non_positive_risk():
    assert compute_position_size(0.0, 100.0, 95.0) is None
    assert compute_position_size(-100.0, 100.0, 95.0) is None


def test_compute_position_size_none_when_too_small_for_one_share():
    assert compute_position_size(1.0, 100.0, 50.0) is None  # risk=1, stop_distance=50 -> 0 shares


def test_compute_risk_reward_long_hand_computed():
    # entry=100, stop=95 (distance=5), target=115 (reward=15) -> RR=3.0
    assert compute_risk_reward(100.0, 95.0, 115.0, "LONG") == pytest.approx(3.0)


def test_compute_risk_reward_short_hand_computed():
    # entry=100, stop=105 (distance=5), target=85 (reward=15) -> RR=3.0
    assert compute_risk_reward(100.0, 105.0, 85.0, "SHORT") == pytest.approx(3.0)


def test_compute_risk_reward_none_without_target():
    assert compute_risk_reward(100.0, 95.0, None, "LONG") is None


def test_compute_risk_reward_none_when_reward_not_positive():
    # target below entry for a LONG -> non-positive reward
    assert compute_risk_reward(100.0, 95.0, 98.0, "LONG") is None
