import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod  # noqa: E402
from app.entry_engine.state_machine import TradeLifecycle  # noqa: E402
from app.paper_trading.engine import PaperTradingEngine  # noqa: E402
from app.paper_trading.integration import paper_trade_from_lifecycle  # noqa: E402


def make_row(**kwargs):
    base = {
        "timestamp": 0, "close": 100.0, "high": 100.0, "low": 100.0,
        "resistance": float("nan"), "support": float("nan"), "atr": float("nan"),
        "swing_low_price": float("nan"), "swing_high_price": float("nan"),
        "r1": float("nan"), "r2": float("nan"), "r3": float("nan"),
        "s1": float("nan"), "s2": float("nan"), "s3": float("nan"),
    }
    base.update(kwargs)
    return pd.Series(base)


def make_setup(**kwargs):
    base = {"long_breakout": False, "long_retest": False, "short_breakdown": False, "short_retest": False}
    base.update(kwargs)
    return pd.Series(base)


def make_triggered_lifecycle() -> TradeLifecycle:
    config = EntryEngineConfig(entry_method=EntryMethod.BREAKOUT, stop_method=StopMethod.SUPPORT_RESISTANCE, target_method=TargetMethod.RISK_REWARD_2)
    lifecycle = TradeLifecycle("LONG", config)
    lifecycle.step(
        make_row(timestamp=1, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0),
        None,
        make_setup(long_breakout=True),
    )
    return lifecycle


def test_paper_trade_from_lifecycle_opens_matching_position():
    lifecycle = make_triggered_lifecycle()
    engine = PaperTradingEngine()

    position = paper_trade_from_lifecycle(
        engine, lifecycle, symbol="RELIANCE", entry_time=1, quantity=100,
        opportunity_score_at_entry=82.0, market_condition="Bullish (ADX 28.0)",
    )

    assert position.symbol == "RELIANCE"
    assert position.direction == "LONG"
    assert position.entry_price == pytest.approx(lifecycle.entry_price)
    assert position.stop_loss == pytest.approx(lifecycle.stop)
    assert position.target == pytest.approx(lifecycle.target)
    assert position.opportunity_score_at_entry == pytest.approx(82.0)
    assert position in engine.get_open_positions()


def test_paper_trade_from_lifecycle_default_reason_mentions_method():
    lifecycle = make_triggered_lifecycle()
    engine = PaperTradingEngine()
    position = paper_trade_from_lifecycle(engine, lifecycle, symbol="RELIANCE", entry_time=1, quantity=100)
    assert "breakout" in position.reason_for_entry.lower()
    assert "LONG" in position.reason_for_entry


def test_paper_trade_from_lifecycle_custom_reason_overrides_default():
    lifecycle = make_triggered_lifecycle()
    engine = PaperTradingEngine()
    position = paper_trade_from_lifecycle(
        engine, lifecycle, symbol="RELIANCE", entry_time=1, quantity=100, reason_for_entry="user override"
    )
    assert position.reason_for_entry == "user override"


def test_paper_trade_from_lifecycle_rejects_non_triggered_state():
    config = EntryEngineConfig(entry_method=EntryMethod.BREAKOUT, stop_method=StopMethod.SUPPORT_RESISTANCE, target_method=TargetMethod.RISK_REWARD_2)
    lifecycle = TradeLifecycle("LONG", config)  # still in SETUP, never stepped
    engine = PaperTradingEngine()
    with pytest.raises(ValueError, match="ENTRY_TRIGGER"):
        paper_trade_from_lifecycle(engine, lifecycle, symbol="RELIANCE", entry_time=1, quantity=100)
