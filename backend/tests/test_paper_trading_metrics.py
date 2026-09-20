import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paper_trading.metrics import (  # noqa: E402
    compute_average_r,
    compute_max_drawdown,
    compute_summary,
    compute_todays_pnl,
    compute_win_rate,
)
from app.paper_trading.models import PaperPosition  # noqa: E402

TODAY = date(2026, 1, 28)
YESTERDAY = date(2026, 1, 27)


def make_closed(pnl, r_multiple, exit_dt):
    return PaperPosition(
        id="x", symbol="TEST", direction="LONG", entry_price=100.0, quantity=100,
        stop_loss=95.0, target=110.0, entry_time=exit_dt,
        exit_time=exit_dt, exit_price=105.0, exit_reason="TARGET_HIT",
        pnl=pnl, pnl_pct=pnl / 100, r_multiple=r_multiple,
    )


def test_todays_pnl_only_sums_positions_closed_today():
    positions = [
        make_closed(1000.0, 2.0, datetime(2026, 1, 28, 10, 0)),
        make_closed(-500.0, -1.0, datetime(2026, 1, 27, 14, 0)),  # yesterday - excluded
        make_closed(300.0, 1.0, datetime(2026, 1, 28, 15, 0)),
    ]
    assert compute_todays_pnl(positions, as_of=TODAY) == pytest.approx(1300.0)
    assert compute_todays_pnl(positions, as_of=YESTERDAY) == pytest.approx(-500.0)


def test_win_rate_hand_computed():
    positions = [
        make_closed(1000.0, 2.0, datetime(2026, 1, 28, 10, 0)),
        make_closed(-500.0, -1.0, datetime(2026, 1, 28, 11, 0)),
        make_closed(300.0, 1.0, datetime(2026, 1, 28, 12, 0)),
    ]
    assert compute_win_rate(positions) == pytest.approx(2 / 3)


def test_win_rate_none_when_no_closed_positions():
    assert compute_win_rate([]) is None


def test_average_r_hand_computed():
    positions = [
        make_closed(1000.0, 2.0, datetime(2026, 1, 28, 10, 0)),
        make_closed(-500.0, -1.0, datetime(2026, 1, 28, 11, 0)),
    ]
    assert compute_average_r(positions) == pytest.approx(0.5)


def test_max_drawdown_hand_computed():
    positions = [
        make_closed(1000.0, 2.0, datetime(2026, 1, 28, 9, 0)),
        make_closed(-1500.0, -1.0, datetime(2026, 1, 28, 10, 0)),
        make_closed(500.0, 1.0, datetime(2026, 1, 28, 11, 0)),
    ]
    # equity: 1000, -500, 0 -> peak=1000, trough=-500 -> dd=1500
    assert compute_max_drawdown(positions) == pytest.approx(1500.0)


def test_compute_summary_bundles_everything():
    open_positions = [make_closed(0, None, datetime(2026, 1, 28, 9, 0))]  # stand-in for an open position count
    closed_positions = [
        make_closed(1000.0, 2.0, datetime(2026, 1, 28, 10, 0)),
        make_closed(-500.0, -1.0, datetime(2026, 1, 28, 11, 0)),
    ]
    summary = compute_summary(open_positions, closed_positions, as_of=TODAY)
    assert summary.open_positions_count == 1
    assert summary.closed_positions_count == 2
    assert summary.todays_pnl == pytest.approx(500.0)
    assert summary.win_rate == pytest.approx(0.5)
    assert summary.average_r == pytest.approx(0.5)
