import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.costs import CostModel  # noqa: E402
from app.paper_trading.models import PaperPosition, close_position  # noqa: E402


def make_position(direction="LONG", entry_price=100.0, quantity=200, stop_loss=95.0, target=115.0):
    return PaperPosition(
        id="p1", symbol="RELIANCE", direction=direction, entry_price=entry_price,
        quantity=quantity, stop_loss=stop_loss, target=target, entry_time=1,
        opportunity_score_at_entry=78.0, market_condition="Bullish (ADX 27.4)",
        reason_for_entry="breakout entry trigger (LONG)",
    )


def test_long_target_hit_hand_computed_no_costs():
    position = make_position()
    closed = close_position(position, exit_time=2, exit_price=115.0, exit_reason="TARGET_HIT")
    assert closed.pnl == pytest.approx(3000.0)         # (115-100)*200
    assert closed.pnl_pct == pytest.approx(15.0)        # 3000/20000*100
    assert closed.r_multiple == pytest.approx(3.0)      # (3000/200)/5
    assert closed.is_win is True
    assert closed.is_open is False


def test_long_target_hit_with_cost_model():
    position = make_position()
    costs = CostModel(brokerage_pct=0.0003, fees_pct=0.0005, slippage_pct=0.0, spread_pct=0.0)
    closed = close_position(position, exit_time=2, exit_price=115.0, exit_reason="TARGET_HIT", cost_model=costs)
    # charges = (20000 + 23000) * 0.0008 = 34.4
    assert closed.pnl == pytest.approx(3000.0 - 34.4)
    # recorded entry/exit prices stay the clean theoretical values
    assert closed.entry_price == pytest.approx(100.0)
    assert closed.exit_price == pytest.approx(115.0)


def test_short_target_hit_hand_computed():
    position = make_position(direction="SHORT", stop_loss=105.0, target=85.0)
    closed = close_position(position, exit_time=2, exit_price=85.0, exit_reason="TARGET_HIT")
    assert closed.pnl == pytest.approx(3000.0)  # (100-85)*200
    assert closed.r_multiple == pytest.approx(3.0)
    assert closed.is_win is True


def test_stop_loss_hit_is_a_loss():
    position = make_position()
    closed = close_position(position, exit_time=2, exit_price=95.0, exit_reason="STOP_LOSS_HIT")
    assert closed.pnl == pytest.approx(-1000.0)  # (95-100)*200
    assert closed.r_multiple == pytest.approx(-1.0)
    assert closed.is_win is False


def test_manual_close_records_reason():
    position = make_position()
    closed = close_position(position, exit_time=2, exit_price=103.0, exit_reason="MANUAL_CLOSE")
    assert closed.exit_reason == "MANUAL_CLOSE"
    assert closed.pnl == pytest.approx(600.0)


def test_open_position_has_no_pnl_or_win_classification():
    position = make_position()
    assert position.is_open is True
    assert position.is_win is None
    assert position.pnl is None


def test_r_multiple_none_when_no_stop_loss():
    position = make_position(stop_loss=None)
    closed = close_position(position, exit_time=2, exit_price=115.0, exit_reason="TARGET_HIT")
    assert closed.r_multiple is None
    assert closed.pnl == pytest.approx(3000.0)  # P&L still computed even without a stop


def test_context_fields_preserved_through_close():
    position = make_position()
    closed = close_position(position, exit_time=2, exit_price=115.0, exit_reason="TARGET_HIT")
    assert closed.opportunity_score_at_entry == pytest.approx(78.0)
    assert closed.market_condition == "Bullish (ADX 27.4)"
    assert closed.reason_for_entry == "breakout entry trigger (LONG)"
