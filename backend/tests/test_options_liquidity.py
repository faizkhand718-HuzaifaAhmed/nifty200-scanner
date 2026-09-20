import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.options_analysis.config import OptionSelectionConfig  # noqa: E402
from app.options_analysis.liquidity import (  # noqa: E402
    LiquidityRating,
    compute_spread_pct,
    passes_liquidity_filter,
    rate_liquidity,
)

CONFIG = OptionSelectionConfig(min_volume=1000, min_open_interest=5000, max_spread_pct=0.05)


def test_compute_spread_pct_hand_computed():
    # bid=98, ask=102 -> mid=100 -> spread=(102-98)/100=0.04
    assert compute_spread_pct(98.0, 102.0) == pytest.approx(0.04)


def test_compute_spread_pct_none_when_missing():
    assert compute_spread_pct(None, 102.0) is None
    assert compute_spread_pct(98.0, None) is None


def test_compute_spread_pct_none_when_crossed_or_zero():
    assert compute_spread_pct(0.0, 0.0) is None
    assert compute_spread_pct(105.0, 100.0) is None  # ask < bid, malformed


def test_passes_liquidity_filter_all_conditions():
    assert passes_liquidity_filter(1000, 5000, 0.05, CONFIG) is True
    assert passes_liquidity_filter(999, 5000, 0.05, CONFIG) is False
    assert passes_liquidity_filter(1000, 4999, 0.05, CONFIG) is False
    assert passes_liquidity_filter(1000, 5000, 0.0501, CONFIG) is False


def test_passes_liquidity_filter_missing_value_fails_not_passes():
    """A missing value must never be treated as 'good enough' by default."""
    assert passes_liquidity_filter(None, 5000, 0.05, CONFIG) is False
    assert passes_liquidity_filter(1000, None, 0.05, CONFIG) is False
    assert passes_liquidity_filter(1000, 5000, None, CONFIG) is False


def test_rate_liquidity_illiquid():
    assert rate_liquidity(500, 1000, 0.1, CONFIG) == LiquidityRating.ILLIQUID


def test_rate_liquidity_acceptable_just_above_thresholds():
    assert rate_liquidity(1000, 5000, 0.05, CONFIG) == LiquidityRating.ACCEPTABLE


def test_rate_liquidity_liquid_comfortably_above_thresholds():
    # 3x volume, 3x OI, half the max spread
    assert rate_liquidity(3000, 15000, 0.024, CONFIG) == LiquidityRating.LIQUID
