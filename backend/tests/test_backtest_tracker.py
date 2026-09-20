import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.config import BacktestConfig  # noqa: E402
from app.backtesting.tracker import SymbolBacktestTracker  # noqa: E402
from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod  # noqa: E402


def ind_row(**kwargs):
    base = {
        "timestamp": 0, "close": 100.0, "high": 100.0, "low": 100.0,
        "resistance": float("nan"), "support": float("nan"), "atr": float("nan"),
        "swing_low_price": float("nan"), "swing_high_price": float("nan"),
        "r1": float("nan"), "r2": float("nan"), "r3": float("nan"),
        "s1": float("nan"), "s2": float("nan"), "s3": float("nan"),
    }
    base.update(kwargs)
    return pd.Series(base)


def setup_row(**kwargs):
    base = {"long_breakout": False, "long_retest": False, "short_breakdown": False, "short_retest": False}
    base.update(kwargs)
    return pd.Series(base)


def scoring_row(long_score=0.0):
    return pd.Series({"long_score": long_score, "short_score": 0.0})


def make_config(**overrides) -> BacktestConfig:
    entry_config = EntryEngineConfig(entry_method=EntryMethod.BREAKOUT, stop_method=StopMethod.SUPPORT_RESISTANCE, target_method=TargetMethod.RISK_REWARD_2)
    cfg = BacktestConfig(direction="LONG", entry_config=entry_config, min_score=60.0)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def run_bars(tracker, bars):
    prev = None
    for ind, setup, scoring in bars:
        tracker.step(ind, prev, setup, scoring)
        prev = ind


def test_no_tracking_below_min_score():
    tracker = SymbolBacktestTracker("TEST", make_config())
    tracker.step(ind_row(timestamp=1, close=98.0, resistance=100.0), None, setup_row(), scoring_row(long_score=50.0))
    assert tracker.current_lifecycle is None
    assert tracker.completed_trades == []


def test_full_trade_lifecycle_completes_and_records():
    tracker = SymbolBacktestTracker("TEST", make_config())
    bars = [
        (ind_row(timestamp=1, close=98.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
        (ind_row(timestamp=2, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), setup_row(long_breakout=True), scoring_row(70.0)),
        (ind_row(timestamp=3, close=124.0, high=125.0, low=123.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
    ]
    run_bars(tracker, bars)

    assert len(tracker.completed_trades) == 1
    trade = tracker.completed_trades[0]
    assert trade.exit_reason == "TARGET_HIT"
    assert trade.entry_price_theoretical == pytest.approx(101.0)
    assert tracker.current_lifecycle is None  # ready to look for the next opportunity


def test_new_trade_starts_after_previous_one_resolves():
    """Multiple trades per symbol over an extended date range."""
    tracker = SymbolBacktestTracker("TEST", make_config())
    bars = [
        # Trade 1: triggers and hits target
        (ind_row(timestamp=1, close=98.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
        (ind_row(timestamp=2, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), setup_row(long_breakout=True), scoring_row(70.0)),
        (ind_row(timestamp=3, close=124.0, high=125.0, low=123.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
        # Trade 2: a fresh setup on a new (higher) resistance level, also triggers and hits target
        (ind_row(timestamp=4, close=128.0, resistance=130.0, support=120.0), setup_row(), scoring_row(70.0)),
        (ind_row(timestamp=5, close=131.0, high=131.5, low=129.5, resistance=130.0, support=120.0), setup_row(long_breakout=True), scoring_row(70.0)),
        (ind_row(timestamp=6, close=155.0, high=156.0, low=154.0, resistance=130.0, support=120.0), setup_row(), scoring_row(70.0)),
    ]
    run_bars(tracker, bars)

    assert len(tracker.completed_trades) == 2
    assert tracker.completed_trades[0].entry_price_theoretical == pytest.approx(101.0)
    assert tracker.completed_trades[1].entry_price_theoretical == pytest.approx(131.0)


def test_setup_abandoned_when_score_drops_before_trigger():
    tracker = SymbolBacktestTracker("TEST", make_config())
    bars = [
        (ind_row(timestamp=1, close=98.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),  # starts tracking
        (ind_row(timestamp=2, close=98.5, resistance=100.0, support=90.0), setup_row(), scoring_row(40.0)),  # score drops - abandon
        (ind_row(timestamp=3, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), setup_row(long_breakout=True), scoring_row(40.0)),  # breakout fires but score still too low to even be watching
    ]
    run_bars(tracker, bars)
    # No trade should exist - tracking was abandoned before the breakout bar,
    # and score never recovered above min_score to start a new one.
    assert tracker.completed_trades == []
    assert tracker.current_lifecycle is None


def test_setup_resumes_if_score_recovers_before_trigger():
    tracker = SymbolBacktestTracker("TEST", make_config())
    bars = [
        (ind_row(timestamp=1, close=98.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
        (ind_row(timestamp=2, close=98.5, resistance=100.0, support=90.0), setup_row(), scoring_row(40.0)),  # abandoned
        (ind_row(timestamp=3, close=99.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),  # score recovers - fresh tracking starts
        (ind_row(timestamp=4, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), setup_row(long_breakout=True), scoring_row(70.0)),
    ]
    run_bars(tracker, bars)
    assert tracker.current_lifecycle is not None
    assert tracker.current_lifecycle.entry_price == pytest.approx(101.0)


def test_finalize_records_open_trade_still_in_position():
    tracker = SymbolBacktestTracker("TEST", make_config())
    bars = [
        (ind_row(timestamp=1, close=98.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
        (ind_row(timestamp=2, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), setup_row(long_breakout=True), scoring_row(70.0)),
        (ind_row(timestamp=3, close=105.0, high=106.0, low=104.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
    ]
    run_bars(tracker, bars)
    assert tracker.completed_trades == []  # neither stop nor target hit yet
    tracker.finalize()
    assert tracker.open_trade is not None
    assert tracker.open_trade.entry_price_theoretical == pytest.approx(101.0)


def test_finalize_records_trade_that_triggered_on_the_very_last_bar():
    """A trade whose entry fires on the LAST bar of the dataset never
    gets a chance to reach POSITION_ACTIVE - it must still be reported as
    open, not silently dropped."""
    tracker = SymbolBacktestTracker("TEST", make_config())
    bars = [
        (ind_row(timestamp=1, close=98.0, resistance=100.0, support=90.0), setup_row(), scoring_row(70.0)),
        (ind_row(timestamp=2, close=101.0, high=101.5, low=99.5, resistance=100.0, support=90.0), setup_row(long_breakout=True), scoring_row(70.0)),
    ]
    run_bars(tracker, bars)
    tracker.finalize()
    assert tracker.open_trade is not None
    assert tracker.completed_trades == []


def test_finalize_no_open_trade_when_nothing_was_tracked():
    tracker = SymbolBacktestTracker("TEST", make_config())
    tracker.step(ind_row(timestamp=1, close=98.0), None, setup_row(), scoring_row(30.0))
    tracker.finalize()
    assert tracker.open_trade is None
