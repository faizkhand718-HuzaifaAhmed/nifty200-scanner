import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_management.daily_state import DailyRiskState  # noqa: E402


def test_has_open_position():
    state = DailyRiskState(current_date=date(2026, 1, 28))
    assert state.has_open_position("RELIANCE") is False
    state.record_trade_opened("RELIANCE")
    assert state.has_open_position("RELIANCE") is True


def test_record_trade_opened_increments_count():
    state = DailyRiskState(current_date=date(2026, 1, 28))
    state.record_trade_opened("RELIANCE")
    state.record_trade_opened("TCS")
    assert state.trades_taken_today == 2
    assert state.open_position_symbols == {"RELIANCE", "TCS"}


def test_record_trade_closed_updates_pnl_and_removes_symbol():
    state = DailyRiskState(current_date=date(2026, 1, 28))
    state.record_trade_opened("RELIANCE")
    state.record_trade_closed("RELIANCE", realized_pnl=500.0)
    assert state.has_open_position("RELIANCE") is False
    assert state.realized_pnl_today == pytest.approx(500.0)


def test_realized_pnl_accumulates_across_multiple_closes():
    state = DailyRiskState(current_date=date(2026, 1, 28))
    state.record_trade_opened("A")
    state.record_trade_opened("B")
    state.record_trade_closed("A", 500.0)
    state.record_trade_closed("B", -200.0)
    assert state.realized_pnl_today == pytest.approx(300.0)


def test_reset_for_new_day_clears_counters_but_not_open_positions():
    state = DailyRiskState(current_date=date(2026, 1, 28))
    state.record_trade_opened("RELIANCE")
    state.record_trade_closed("TCS", 100.0)  # closing a symbol never opened is harmless
    state.reset_for_new_day(date(2026, 1, 29))

    assert state.current_date == date(2026, 1, 29)
    assert state.trades_taken_today == 0
    assert state.realized_pnl_today == pytest.approx(0.0)
    assert state.has_open_position("RELIANCE") is True  # still open, carried into the new day
