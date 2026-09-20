import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.position_sizing import compute_quantity  # noqa: E402


def test_compute_quantity_hand_computed():
    # capital=100000, risk_pct=0.01 -> risk_amount=1000
    # entry=100, stop=95 -> risk_per_share=5 -> quantity=1000/5=200
    qty = compute_quantity(capital=100000.0, risk_per_trade_pct=0.01, entry_price=100.0, stop_price=95.0)
    assert qty == 200


def test_compute_quantity_rounds_down():
    # risk_amount=1000, risk_per_share=3 -> 333.33 -> 333
    qty = compute_quantity(capital=100000.0, risk_per_trade_pct=0.01, entry_price=100.0, stop_price=97.0)
    assert qty == 333


def test_compute_quantity_none_when_zero_risk_per_share():
    qty = compute_quantity(capital=100000.0, risk_per_trade_pct=0.01, entry_price=100.0, stop_price=100.0)
    assert qty is None


def test_compute_quantity_none_when_capital_non_positive():
    assert compute_quantity(0.0, 0.01, 100.0, 95.0) is None
    assert compute_quantity(-100.0, 0.01, 100.0, 95.0) is None


def test_compute_quantity_none_when_too_small_for_one_share():
    # risk_amount tiny relative to risk_per_share -> quantity rounds to 0
    qty = compute_quantity(capital=10.0, risk_per_trade_pct=0.01, entry_price=100.0, stop_price=50.0)
    assert qty is None
