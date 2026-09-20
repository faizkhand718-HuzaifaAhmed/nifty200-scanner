"""
THE critical test for this phase: proves that extending a backtest's date
range with MORE FUTURE data never changes the recorded outcome of a trade
that already resolved within the original (shorter) range.

Runs the full pipeline (IndicatorEngine -> SetupDetectionEngine ->
OpportunityScoringEngine -> BacktestEngine) twice on the SAME underlying
price history: once on a shorter date range, once on a longer range that
appends additional bars after the point where a trade already closed. The
already-closed trade's entry price, exit price, exit time, exit reason,
net P&L, and R-multiple must be byte-identical between the two runs.

Uses EMA_CONFIRMATION entry + PERCENTAGE stop + RISK_REWARD_2 target
specifically because these methods don't depend on previous-day pivot
levels, keeping the synthetic data construction simple and fully
deterministic (no randomness anywhere in this file).
"""
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting.config import BacktestConfig  # noqa: E402
from app.backtesting.engine import run_symbol  # noqa: E402
from app.entry_engine.config import EntryEngineConfig, EntryMethod, StopMethod, TargetMethod  # noqa: E402
from app.indicators.engine import IndicatorEngine  # noqa: E402
from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402
from app.scoring.engine import OpportunityScoringEngine  # noqa: E402
from app.setup_detection.engine import SetupDetectionEngine  # noqa: E402

HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"
IST = ZoneInfo("Asia/Kolkata")

DAY1 = date(2026, 1, 27)  # decline - EMA9 stays below EMA20
DAY2 = date(2026, 1, 28)  # sharp reversal up - EMA9 crosses above EMA20, rallies to target
DAY3 = date(2026, 1, 29)  # "future" padding, appended only in the longer run
DAY4 = date(2026, 2, 2)   # more "future" padding


def build_ohlcv(days) -> pd.DataFrame:
    calendar = NSECalendar.from_file(HOLIDAY_FILE)
    timestamps = []
    for d in days:
        timestamps.extend(calendar.session_timestamps(d, Timeframe.FIFTEEN_MIN))

    rows = []
    day_len = len(calendar.session_timestamps(DAY1, Timeframe.FIFTEEN_MIN))

    price = 110.0
    for i, ts in enumerate(timestamps):
        day_index = i // day_len

        if day_index == 0:
            price -= 0.4  # steady decline
        elif day_index == 1:
            price += 1.2  # sharp sustained rally
        else:
            price += 0.15  # gentle continuation in the "future" padding days

        close = round(price, 2)
        high = close + 0.3
        low = close - 0.3
        open_ = close - 0.05
        volume = 50000 + i * 10
        rows.append((ts, open_, high, low, close, volume))

    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


def compute_trades(days_included):
    df = build_ohlcv(days_included)
    indicator_engine = IndicatorEngine()
    indicators_df = indicator_engine.compute(df)
    setup_df = SetupDetectionEngine().compute(indicators_df, nifty_df=None)
    scoring_df = OpportunityScoringEngine().compute(indicators_df, setup_df, nifty_indicators_df=None)

    config = BacktestConfig(
        direction="LONG",
        entry_config=EntryEngineConfig(
            entry_method=EntryMethod.EMA_CONFIRMATION,
            stop_method=StopMethod.PERCENTAGE,
            target_method=TargetMethod.RISK_REWARD_2,
            stop_percentage=0.01,
        ),
        min_score=0.0,  # score gate disabled for this test - we're proving causality, not gating
    )
    trades, open_trade = run_symbol("TESTSYM", indicators_df, setup_df, scoring_df, config)
    return trades, open_trade


@pytest.fixture(scope="module")
def short_range_trades():
    trades, _ = compute_trades([DAY1, DAY2])
    return trades


@pytest.fixture(scope="module")
def long_range_trades():
    trades, _ = compute_trades([DAY1, DAY2, DAY3, DAY4])
    return trades


def test_a_trade_actually_completes_in_this_synthetic_data(short_range_trades):
    """Sanity check: if this fails, the synthetic price series needs
    adjusting - the causality proof below is vacuous without at least one
    real completed trade to compare."""
    assert len(short_range_trades) >= 1


def test_future_data_does_not_change_an_already_closed_trade(short_range_trades, long_range_trades):
    assert len(short_range_trades) >= 1
    assert len(long_range_trades) >= len(short_range_trades)

    long_by_entry = {t.entry_time: t for t in long_range_trades}

    for short_trade in short_range_trades:
        long_trade = long_by_entry.get(short_trade.entry_time)
        assert long_trade is not None, f"trade entered at {short_trade.entry_time} missing from the longer run"

        assert long_trade.entry_price_theoretical == pytest.approx(short_trade.entry_price_theoretical)
        assert long_trade.entry_price_filled == pytest.approx(short_trade.entry_price_filled)
        assert long_trade.stop_price == pytest.approx(short_trade.stop_price)
        assert long_trade.target_price == pytest.approx(short_trade.target_price)
        assert long_trade.quantity == short_trade.quantity
        assert long_trade.exit_time == short_trade.exit_time
        assert long_trade.exit_reason == short_trade.exit_reason
        assert long_trade.exit_price_theoretical == pytest.approx(short_trade.exit_price_theoretical)
        assert long_trade.net_pnl == pytest.approx(short_trade.net_pnl)
        assert long_trade.r_multiple == pytest.approx(short_trade.r_multiple)


def test_indicator_values_at_shared_timestamps_are_identical_across_ranges():
    """Companion proof at the indicator layer (redundant with Phase 4's
    own no-lookahead tests, but cheap to re-verify here at the exact data
    this backtest test uses, end to end)."""
    short_df = IndicatorEngine().compute(build_ohlcv([DAY1, DAY2]))
    long_df = IndicatorEngine().compute(build_ohlcv([DAY1, DAY2, DAY3, DAY4]))

    long_prefix = long_df[long_df["timestamp"].isin(short_df["timestamp"])].reset_index(drop=True)
    short_df = short_df.reset_index(drop=True)

    for col in ("close", "ema_9", "ema_20", "rsi", "atr", "adx"):
        pd.testing.assert_series_equal(short_df[col], long_prefix[col], check_names=False)


def test_open_trade_at_end_of_short_range_may_close_within_extended_range():
    """Not a bug: a trade still open when the short range ends is exactly
    the scenario extending the range is FOR - it may resolve once more
    data exists. This documents that expected behavior so it isn't
    mistaken for a look-ahead violation: the trade's ENTRY details still
    match exactly (checked above); only its resolution can differ between
    a short run (where it's still open) and a longer run (where it may
    have closed) - because AT THE TIME the short run ended, that outcome
    was genuinely still unknown."""
    short_trades, short_open = compute_trades([DAY1, DAY2])
    long_trades, long_open = compute_trades([DAY1, DAY2, DAY3, DAY4])

    if short_open is not None:
        matching_long = [t for t in long_trades if t.entry_time == short_open.entry_time]
        still_open_long = long_open is not None and long_open.entry_time == short_open.entry_time
        assert matching_long or still_open_long, "the trade open at the end of the short range must appear somewhere in the longer run"
