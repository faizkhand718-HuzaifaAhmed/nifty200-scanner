import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.costs import CostModel  # noqa: E402
from app.backtesting.trade_record import build_trade_record, close_trade  # noqa: E402

COSTS = CostModel(brokerage_pct=0.0003, fees_pct=0.0005, slippage_pct=0.001, spread_pct=0.0005)


def test_long_winning_trade_hand_computed():
    trade = build_trade_record(
        symbol="RELIANCE", direction="LONG", entry_time=1, entry_price_theoretical=100.0,
        stop_price=95.0, target_price=115.0, quantity=200, costs=COSTS,
    )
    # entry_fill = 100 * 1.0015 = 100.15
    assert trade.entry_price_filled == pytest.approx(100.15)
    assert trade.is_closed is False
    assert trade.is_win is None  # not yet resolved

    closed = close_trade(trade, exit_time=2, exit_price_theoretical=115.0, exit_reason="TARGET_HIT", costs=COSTS)
    # exit_fill = 115 * 0.9985 = 114.8275
    assert closed.exit_price_filled == pytest.approx(114.8275)
    # gross = (114.8275 - 100.15) * 200 = 2935.5
    assert closed.gross_pnl == pytest.approx(2935.5)
    # charges = (20030 + 22965.5) * 0.0008 = 42995.5 * 0.0008 = 34.3964
    assert closed.charges == pytest.approx(34.3964)
    assert closed.net_pnl == pytest.approx(2935.5 - 34.3964)
    assert closed.is_win is True
    # r_multiple = net_pnl_per_share / risk_per_share = (net_pnl/200) / 5
    expected_r = (closed.net_pnl / 200) / 5.0
    assert closed.r_multiple == pytest.approx(expected_r)


def test_target_hit_can_still_be_a_net_loss_after_costs():
    """The central financial-correctness requirement: a trade that
    technically hits its target on a very tight move can still be a net
    loser once realistic costs are applied - 'winning' must be judged by
    net P&L, never by exit_reason alone."""
    trade = build_trade_record(
        symbol="RELIANCE", direction="LONG", entry_time=1, entry_price_theoretical=100.0,
        stop_price=95.0, target_price=100.3, quantity=200, costs=COSTS,
    )
    closed = close_trade(trade, exit_time=2, exit_price_theoretical=100.3, exit_reason="TARGET_HIT", costs=COSTS)

    assert closed.exit_reason == "TARGET_HIT"
    assert closed.net_pnl < 0
    assert closed.is_win is False


def test_short_winning_trade_hand_computed():
    trade = build_trade_record(
        symbol="ZOMATO", direction="SHORT", entry_time=1, entry_price_theoretical=100.0,
        stop_price=105.0, target_price=85.0, quantity=200, costs=COSTS,
    )
    # short entry fill = 100 * 0.9985 = 99.85
    assert trade.entry_price_filled == pytest.approx(99.85)

    closed = close_trade(trade, exit_time=2, exit_price_theoretical=85.0, exit_reason="TARGET_HIT", costs=COSTS)
    # short exit (buy to cover) fill = 85 * 1.0015 = 85.1275
    assert closed.exit_price_filled == pytest.approx(85.1275)
    # gross = (entry_fill - exit_fill) * qty = (99.85 - 85.1275) * 200 = 2944.5
    assert closed.gross_pnl == pytest.approx(2944.5)
    assert closed.is_win is True


def test_stop_loss_hit_is_a_loss():
    trade = build_trade_record(
        symbol="RELIANCE", direction="LONG", entry_time=1, entry_price_theoretical=100.0,
        stop_price=95.0, target_price=115.0, quantity=200, costs=COSTS,
    )
    closed = close_trade(trade, exit_time=2, exit_price_theoretical=95.0, exit_reason="STOP_LOSS_HIT", costs=COSTS)
    assert closed.net_pnl < 0
    assert closed.is_win is False
    assert closed.r_multiple < 0


def test_open_trade_has_no_win_loss_classification():
    trade = build_trade_record(
        symbol="RELIANCE", direction="LONG", entry_time=1, entry_price_theoretical=100.0,
        stop_price=95.0, target_price=115.0, quantity=200, costs=COSTS,
    )
    assert trade.is_closed is False
    assert trade.is_win is None
    assert trade.net_pnl is None
