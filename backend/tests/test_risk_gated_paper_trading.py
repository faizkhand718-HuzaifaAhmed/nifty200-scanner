import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paper_trading.engine import PaperTradingEngine  # noqa: E402
from app.paper_trading.risk_gated_engine import RiskGatedPaperTradingEngine  # noqa: E402
from app.risk_management.config import RiskConfig  # noqa: E402
from app.risk_management.engine import RiskManager  # noqa: E402
from app.risk_management.models import ProposedTrade  # noqa: E402

NOW = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)


def make_gated_engine(**config_overrides):
    risk_manager = RiskManager(RiskConfig(account_capital=100000.0, **config_overrides), today=date(2026, 1, 28))
    return RiskGatedPaperTradingEngine(risk_manager)


def make_trade(symbol="RELIANCE", entry=100.0, stop=95.0, target=115.0):
    return ProposedTrade(symbol=symbol, direction="LONG", entry_price=entry, stop_loss=stop, target=target, market_data_timestamp=NOW)


def test_first_open_succeeds_with_correct_position_size():
    engine = make_gated_engine(risk_per_trade_pct=0.01, max_loss_per_trade=5000.0)
    result = engine.try_open_position(make_trade(), now=NOW)
    assert result.opened is True
    assert result.position.quantity == 200  # 1% of 100000 = 1000 risk / 5 stop distance


def test_duplicate_is_blocked_this_is_the_gap_this_class_fixes():
    """THE regression test for the QA finding: using PaperTradingEngine
    directly allowed duplicate positions in the same symbol.
    RiskGatedPaperTradingEngine must not."""
    engine = make_gated_engine()
    first = engine.try_open_position(make_trade(symbol="RELIANCE"), now=NOW)
    assert first.opened is True

    second = engine.try_open_position(make_trade(symbol="RELIANCE"), now=NOW)
    assert second.opened is False
    assert any("already open" in r for r in second.decision.rejection_reasons)

    reliance_positions = [p for p in engine.paper_engine.get_open_positions() if p.symbol == "RELIANCE"]
    assert len(reliance_positions) == 1


def test_daily_loss_limit_blocks_further_opens():
    engine = make_gated_engine(max_daily_loss=1000.0)
    opened = engine.try_open_position(make_trade(symbol="A"), now=NOW)
    assert opened.opened is True
    engine.close_position(opened.position.id, exit_time=NOW, exit_price=90.0)  # a loss

    blocked = engine.try_open_position(make_trade(symbol="B"), now=NOW)
    assert blocked.opened is False
    assert any("daily loss limit" in r for r in blocked.decision.rejection_reasons)


def test_close_position_updates_both_engines_state():
    engine = make_gated_engine()
    opened = engine.try_open_position(make_trade(symbol="RELIANCE"), now=NOW)
    assert engine.risk_manager.state.has_open_position("RELIANCE") is True

    closed = engine.close_position(opened.position.id, exit_time=NOW, exit_price=110.0)
    assert closed.exit_price == pytest.approx(110.0)
    assert engine.paper_engine.get_position(opened.position.id).is_open is False
    assert engine.risk_manager.state.has_open_position("RELIANCE") is False
    assert engine.risk_manager.state.realized_pnl_today == pytest.approx(closed.pnl)


def test_after_close_the_same_symbol_can_be_reopened():
    engine = make_gated_engine()
    opened = engine.try_open_position(make_trade(symbol="RELIANCE"), now=NOW)
    engine.close_position(opened.position.id, exit_time=NOW, exit_price=110.0)

    reopened = engine.try_open_position(make_trade(symbol="RELIANCE"), now=NOW)
    assert reopened.opened is True


def test_stale_data_blocks_open_before_paper_engine_is_ever_touched():
    engine = make_gated_engine(max_data_age_seconds=60.0)
    stale_trade = ProposedTrade(
        symbol="RELIANCE", direction="LONG", entry_price=100.0, stop_loss=95.0, target=115.0,
        market_data_timestamp=datetime(2026, 1, 28, 9, 0, tzinfo=timezone.utc),
    )
    result = engine.try_open_position(stale_trade, now=NOW)
    assert result.opened is False
    assert engine.paper_engine.get_open_positions() == []


def test_shared_paper_engine_can_be_passed_in():
    shared_paper_engine = PaperTradingEngine()
    risk_manager = RiskManager(RiskConfig(account_capital=100000.0), today=date(2026, 1, 28))
    gated = RiskGatedPaperTradingEngine(risk_manager, paper_engine=shared_paper_engine)
    gated.try_open_position(make_trade(), now=NOW)
    assert len(shared_paper_engine.get_open_positions()) == 1
