import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.costs import (  # noqa: E402
    CostModel,
    cash_charges,
    fill_price_long_entry,
    fill_price_long_exit,
    fill_price_short_entry,
    fill_price_short_exit,
)

COSTS = CostModel(brokerage_pct=0.0003, fees_pct=0.0005, slippage_pct=0.001, spread_pct=0.0005)


def test_long_entry_fill_is_worse_higher():
    # 100 * (1 + 0.001 + 0.0005) = 100.15
    assert fill_price_long_entry(100.0, COSTS) == pytest.approx(100.15)


def test_long_exit_fill_is_worse_lower():
    assert fill_price_long_exit(100.0, COSTS) == pytest.approx(99.85)


def test_short_entry_fill_is_worse_lower():
    assert fill_price_short_entry(100.0, COSTS) == pytest.approx(99.85)


def test_short_exit_fill_is_worse_higher():
    assert fill_price_short_exit(100.0, COSTS) == pytest.approx(100.15)


def test_cash_charges_hand_computed():
    # (10000 + 10015) * (0.0003 + 0.0005) = 20015 * 0.0008 = 16.012
    result = cash_charges(entry_value=10000.0, exit_value=10015.0, costs=COSTS)
    assert result == pytest.approx(16.012)


def test_zero_cost_model_means_no_adjustment():
    zero = CostModel(brokerage_pct=0.0, fees_pct=0.0, slippage_pct=0.0, spread_pct=0.0)
    assert fill_price_long_entry(100.0, zero) == pytest.approx(100.0)
    assert cash_charges(10000.0, 10000.0, zero) == pytest.approx(0.0)


def test_validate_rejects_negative():
    with pytest.raises(ValueError):
        CostModel(slippage_pct=-0.001).validate()
