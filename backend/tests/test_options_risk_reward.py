import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.options_analysis.option_risk_reward import compute_option_risk_reward, estimate_intrinsic_value  # noqa: E402


def test_estimate_intrinsic_value_call():
    assert estimate_intrinsic_value(1100.0, 1000.0, "CE") == pytest.approx(100.0)
    assert estimate_intrinsic_value(900.0, 1000.0, "CE") == pytest.approx(0.0)  # OTM, floored at 0


def test_estimate_intrinsic_value_put():
    assert estimate_intrinsic_value(900.0, 1000.0, "PE") == pytest.approx(100.0)
    assert estimate_intrinsic_value(1100.0, 1000.0, "PE") == pytest.approx(0.0)


def test_compute_option_risk_reward_call_hand_computed():
    # premium=50, strike=1000, target=1100 -> intrinsic@target=100, reward=50
    # stop=950 -> intrinsic@stop=0, risk=50 -> R:R = 1.0
    rr = compute_option_risk_reward(current_premium=50.0, strike=1000.0, option_type="CE", underlying_stop=950.0, underlying_target=1100.0)
    assert rr == pytest.approx(1.0)


def test_compute_option_risk_reward_put_hand_computed():
    rr = compute_option_risk_reward(current_premium=50.0, strike=1000.0, option_type="PE", underlying_stop=1050.0, underlying_target=900.0)
    assert rr == pytest.approx(1.0)


def test_compute_option_risk_reward_none_without_stop_or_target():
    assert compute_option_risk_reward(50.0, 1000.0, "CE", None, 1100.0) is None
    assert compute_option_risk_reward(50.0, 1000.0, "CE", 950.0, None) is None


def test_compute_option_risk_reward_none_when_risk_not_positive():
    # stop intrinsic value (60) exceeds current premium (50) -> risk <= 0
    rr = compute_option_risk_reward(current_premium=50.0, strike=1000.0, option_type="CE", underlying_stop=1060.0, underlying_target=1200.0)
    assert rr is None


def test_compute_option_risk_reward_none_for_non_positive_premium():
    assert compute_option_risk_reward(0.0, 1000.0, "CE", 950.0, 1100.0) is None
