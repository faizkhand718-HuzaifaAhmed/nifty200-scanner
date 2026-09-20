import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_management.config import RiskConfig  # noqa: E402
from app.risk_management.daily_state import DailyRiskState  # noqa: E402
from app.risk_management.engine import RiskManager  # noqa: E402
from app.risk_management.models import ProposedTrade  # noqa: E402

NOW = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)


def make_manager(**config_overrides):
    config = RiskConfig(account_capital=100000.0, risk_per_trade_pct=0.01, max_loss_per_trade=5000.0, **config_overrides)
    return RiskManager(config, today=date(2026, 1, 28))


def make_trade(symbol="RELIANCE", direction="LONG", entry=100.0, stop=95.0, target=115.0, data_age_seconds=0):
    return ProposedTrade(
        symbol=symbol, direction=direction, entry_price=entry, stop_loss=stop, target=target,
        market_data_timestamp=NOW - timedelta(seconds=data_age_seconds),
    )


def test_approved_trade_hand_computed_position_size():
    manager = make_manager()
    decision = manager.evaluate_trade(make_trade(), now=NOW)
    assert decision.approved is True
    # risk_amount = 1% of 100000 = 1000 ; stop_distance=5 -> qty=200
    assert decision.position_size == 200
    assert decision.risk_amount == pytest.approx(1000.0)
    assert decision.position_value == pytest.approx(200 * 100.0)
    assert decision.risk_reward == pytest.approx(3.0)  # (115-100)/5
    assert decision.warnings == []


def test_position_size_capped_by_max_position_value():
    manager = make_manager(max_position_value=10000.0)  # caps well below the natural 200-share size
    decision = manager.evaluate_trade(make_trade(), now=NOW)
    assert decision.approved is True
    # capped_quantity = floor(10000/100) = 100, well below the natural 200
    assert decision.position_size == 100
    assert decision.position_value == pytest.approx(10000.0)


def test_rejected_when_max_position_value_below_one_share_price():
    manager = make_manager(max_position_value=50.0)  # can't even afford 1 share at price 100
    decision = manager.evaluate_trade(make_trade(entry=100.0, stop=95.0), now=NOW)
    assert decision.approved is False
    assert any("max_position_value" in r for r in decision.rejection_reasons)


def test_stale_market_data_is_rejected():
    manager = make_manager(max_data_age_seconds=60.0)
    decision = manager.evaluate_trade(make_trade(data_age_seconds=120), now=NOW)
    assert decision.approved is False
    assert any("stale" in r for r in decision.rejection_reasons)


def test_fresh_market_data_is_not_rejected_for_staleness():
    manager = make_manager(max_data_age_seconds=60.0)
    decision = manager.evaluate_trade(make_trade(data_age_seconds=30), now=NOW)
    assert decision.approved is True


def test_daily_loss_limit_stops_new_trades():
    manager = make_manager(max_daily_loss=2000.0)
    manager.record_trade_opened("TCS")
    manager.record_trade_closed("TCS", realized_pnl=-2000.0)  # exactly at the limit

    decision = manager.evaluate_trade(make_trade(symbol="RELIANCE"), now=NOW)
    assert decision.approved is False
    assert any("daily loss limit" in r for r in decision.rejection_reasons)


def test_daily_loss_limit_not_triggered_when_below_limit():
    manager = make_manager(max_daily_loss=2000.0)
    manager.record_trade_opened("TCS")
    manager.record_trade_closed("TCS", realized_pnl=-1000.0)  # under the limit

    decision = manager.evaluate_trade(make_trade(symbol="RELIANCE"), now=NOW)
    assert decision.approved is True


def test_max_trades_per_day():
    manager = make_manager(max_trades_per_day=2)
    manager.record_trade_opened("A")
    manager.record_trade_closed("A", 0.0)
    manager.record_trade_opened("B")
    manager.record_trade_closed("B", 0.0)

    decision = manager.evaluate_trade(make_trade(symbol="C"), now=NOW)
    assert decision.approved is False
    assert any("maximum trades per day" in r for r in decision.rejection_reasons)


def test_max_open_positions():
    manager = make_manager(max_open_positions=2)
    manager.record_trade_opened("A")
    manager.record_trade_opened("B")

    decision = manager.evaluate_trade(make_trade(symbol="C"), now=NOW)
    assert decision.approved is False
    assert any("maximum open positions" in r for r in decision.rejection_reasons)


def test_duplicate_position_rejected():
    manager = make_manager()
    manager.record_trade_opened("RELIANCE")

    decision = manager.evaluate_trade(make_trade(symbol="RELIANCE"), now=NOW)
    assert decision.approved is False
    assert any("already open" in r for r in decision.rejection_reasons)


def test_different_symbol_not_treated_as_duplicate():
    manager = make_manager()
    manager.record_trade_opened("RELIANCE")

    decision = manager.evaluate_trade(make_trade(symbol="TCS"), now=NOW)
    assert decision.approved is True


def test_risk_reward_below_minimum_is_a_warning_not_a_rejection():
    manager = make_manager(min_risk_reward=2.0)
    # entry=100, stop=95 (distance 5), target=105 (reward 5) -> RR=1.0, below min 2.0
    decision = manager.evaluate_trade(make_trade(target=105.0), now=NOW)
    assert decision.approved is True  # NOT rejected
    assert any("Risk/Reward" in w for w in decision.warnings)


def test_risk_reward_above_minimum_has_no_warning():
    manager = make_manager(min_risk_reward=2.0)
    decision = manager.evaluate_trade(make_trade(target=115.0), now=NOW)  # RR=3.0
    assert decision.approved is True
    assert decision.warnings == []


def test_no_stop_loss_distance_is_rejected():
    manager = make_manager()
    decision = manager.evaluate_trade(make_trade(entry=100.0, stop=100.0), now=NOW)
    assert decision.approved is False


def test_full_lifecycle_open_then_close_updates_state():
    manager = make_manager()
    decision = manager.evaluate_trade(make_trade(symbol="RELIANCE"), now=NOW)
    assert decision.approved is True

    manager.record_trade_opened("RELIANCE")
    assert manager.state.has_open_position("RELIANCE") is True

    dup_decision = manager.evaluate_trade(make_trade(symbol="RELIANCE"), now=NOW)
    assert dup_decision.approved is False

    manager.record_trade_closed("RELIANCE", realized_pnl=1500.0)
    assert manager.state.has_open_position("RELIANCE") is False
    assert manager.state.realized_pnl_today == pytest.approx(1500.0)

    reopened = manager.evaluate_trade(make_trade(symbol="RELIANCE"), now=NOW)
    assert reopened.approved is True


def test_reset_for_new_day_allows_trading_again_after_daily_loss_limit():
    manager = make_manager(max_daily_loss=1000.0)
    manager.record_trade_opened("A")
    manager.record_trade_closed("A", realized_pnl=-1000.0)
    assert manager.evaluate_trade(make_trade(symbol="B"), now=NOW).approved is False

    manager.reset_for_new_day(date(2026, 1, 29))
    assert manager.evaluate_trade(make_trade(symbol="B"), now=NOW).approved is True


def test_manager_constructor_validates_config():
    with pytest.raises(ValueError):
        RiskManager(RiskConfig(account_capital=-1.0))


def test_manager_accepts_externally_supplied_state():
    shared_state = DailyRiskState(current_date=date(2026, 1, 28))
    manager = RiskManager(RiskConfig(account_capital=100000.0), state=shared_state)
    manager.record_trade_opened("RELIANCE")
    assert shared_state.has_open_position("RELIANCE") is True  # same object, mutated in place
