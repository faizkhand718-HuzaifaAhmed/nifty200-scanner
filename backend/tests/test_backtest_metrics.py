import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.metrics import compute_report  # noqa: E402
from app.backtesting.trade_record import TradeRecord  # noqa: E402


def make_trade(net_pnl, r_multiple, exit_time, exit_reason="TARGET_HIT"):
    return TradeRecord(
        symbol="TEST", direction="LONG", entry_time=exit_time - 1,
        entry_price_theoretical=100.0, entry_price_filled=100.1,
        stop_price=95.0, target_price=110.0, quantity=100,
        exit_time=exit_time, exit_price_theoretical=105.0, exit_price_filled=104.9,
        exit_reason=exit_reason, gross_pnl=net_pnl, charges=0.0, net_pnl=net_pnl, r_multiple=r_multiple,
    )


def test_report_hand_computed():
    trades = [
        make_trade(1000.0, 2.0, exit_time=1),
        make_trade(-500.0, -1.0, exit_time=2, exit_reason="STOP_LOSS_HIT"),
        make_trade(2000.0, 3.0, exit_time=3),
        make_trade(-1000.0, -1.0, exit_time=4, exit_reason="STOP_LOSS_HIT"),
        make_trade(500.0, 1.0, exit_time=5),
    ]
    report = compute_report(trades)

    assert report.total_trades == 5
    assert report.winning_trades == 3
    assert report.losing_trades == 2
    assert report.win_rate == pytest.approx(0.6)
    assert report.average_win == pytest.approx(3500.0 / 3)
    assert report.average_loss == pytest.approx(-750.0)
    assert report.profit_factor == pytest.approx(3500.0 / 1500.0)
    assert report.total_pnl == pytest.approx(2000.0)
    assert report.expectancy == pytest.approx(400.0)
    assert report.average_r == pytest.approx(0.8)
    assert report.max_drawdown == pytest.approx(1000.0)
    assert report.open_trades_count == 0


def test_report_empty_trade_list():
    report = compute_report([])
    assert report.total_trades == 0
    assert report.win_rate is None
    assert report.average_win is None
    assert report.average_loss is None
    assert report.profit_factor is None
    assert report.average_r is None
    assert report.expectancy is None
    assert report.total_pnl == 0.0
    assert report.max_drawdown == 0.0


def test_report_no_losses_profit_factor_is_none_not_infinite():
    trades = [make_trade(1000.0, 2.0, exit_time=1), make_trade(500.0, 1.0, exit_time=2)]
    report = compute_report(trades)
    assert report.losing_trades == 0
    assert report.profit_factor is None  # undefined, not fabricated as infinity


def test_report_open_trades_counted_separately_not_in_stats():
    closed = [make_trade(1000.0, 2.0, exit_time=1)]
    open_trades = [make_trade(0.0, None, exit_time=2, exit_reason="STILL_OPEN")]
    report = compute_report(closed, open_trades=open_trades)
    assert report.total_trades == 1  # open trade excluded from the count
    assert report.open_trades_count == 1


def test_max_drawdown_zero_for_all_winning_trades():
    trades = [make_trade(100.0, 1.0, exit_time=1), make_trade(200.0, 1.0, exit_time=2)]
    report = compute_report(trades)
    assert report.max_drawdown == pytest.approx(0.0)


def test_max_drawdown_sorts_by_exit_time_not_input_order():
    # Deliberately out of order input - report must sort by exit_time.
    trades = [
        make_trade(-1000.0, -1.0, exit_time=4, exit_reason="STOP_LOSS_HIT"),
        make_trade(1000.0, 2.0, exit_time=1),
        make_trade(500.0, 1.0, exit_time=5),
        make_trade(2000.0, 3.0, exit_time=3),
        make_trade(-500.0, -1.0, exit_time=2, exit_reason="STOP_LOSS_HIT"),
    ]
    report = compute_report(trades)
    assert report.max_drawdown == pytest.approx(1000.0)  # same as the ordered test above
