import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.engine import IndicatorEngine  # noqa: E402
from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402

HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"
DAY1 = date(2026, 1, 27)
DAY2 = date(2026, 1, 28)


def build_two_day_ohlcv() -> pd.DataFrame:
    """Two consecutive trading days of synthetic 5-min OHLCV, built on the
    real NSE session grid so timestamps are realistic without depending on
    the (untested-here) MockDataProvider."""
    calendar = NSECalendar.from_file(HOLIDAY_FILE)
    timestamps = calendar.session_timestamps(DAY1, Timeframe.FIVE_MIN) + calendar.session_timestamps(
        DAY2, Timeframe.FIVE_MIN
    )

    rows = []
    price = 100.0
    for i, ts in enumerate(timestamps):
        price += 0.1 if i % 3 != 0 else -0.05  # gentle deterministic drift
        close = round(price, 2)
        open_ = close - 0.05
        high = close + 0.3
        low = close - 0.3
        volume = 1000 + i * 5
        rows.append((ts, open_, high, low, close, volume))

    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


@pytest.fixture()
def engine():
    return IndicatorEngine()


def test_compute_produces_all_expected_columns(engine):
    df = build_two_day_ohlcv()
    result = engine.compute(df)

    expected_columns = {
        "ema_9", "ema_20", "ema_50", "ema_200",
        "macd", "macd_signal", "macd_histogram",
        "rsi", "atr", "plus_di", "minus_di", "adx",
        "vwap", "average_volume", "relative_volume",
        "day_high", "day_low", "prev_day_high", "prev_day_low", "prev_day_close",
        "opening_range_high", "opening_range_low",
        "pivot", "r1", "r2", "r3", "s1", "s2", "s3", "support", "resistance",
        "breakout", "breakdown",
        "swing_high_confirmed", "swing_high_price", "swing_low_confirmed", "swing_low_price",
        "higher_high", "lower_high", "higher_low", "lower_low",
    }
    assert expected_columns.issubset(set(result.columns))
    assert len(result) == len(df)


def test_compute_does_not_mutate_input(engine):
    df = build_two_day_ohlcv()
    original_columns = list(df.columns)
    engine.compute(df)
    assert list(df.columns) == original_columns  # input untouched


def test_compute_rejects_missing_columns(engine):
    df = build_two_day_ohlcv().drop(columns=["volume"])
    with pytest.raises(ValueError, match="missing required columns"):
        engine.compute(df)


def test_compute_rejects_unsorted_timestamps(engine):
    df = build_two_day_ohlcv()
    shuffled = df.iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="sorted ascending"):
        engine.compute(shuffled)


def test_prev_day_high_matches_prior_days_actual_max(engine):
    df = build_two_day_ohlcv()
    result = engine.compute(df)

    day1_mask = result["timestamp"].dt.date == DAY1
    day2_mask = result["timestamp"].dt.date == DAY2

    day1_actual_high = result.loc[day1_mask, "high"].max()
    day2_prev_high_values = result.loc[day2_mask, "prev_day_high"].unique()

    assert len(day2_prev_high_values) == 1
    assert day2_prev_high_values[0] == pytest.approx(day1_actual_high)


def test_day_high_resets_between_sessions(engine):
    df = build_two_day_ohlcv()
    result = engine.compute(df)

    day1_mask = result["timestamp"].dt.date == DAY1
    day2_mask = result["timestamp"].dt.date == DAY2

    day1_final_day_high = result.loc[day1_mask, "day_high"].iloc[-1]
    day2_first_day_high = result.loc[day2_mask, "day_high"].iloc[0]
    day2_first_actual_high = result.loc[day2_mask, "high"].iloc[0]

    # Day 2's first bar's day_high must equal day 2's own first bar high,
    # NOT be inherited/carried over from day 1's running high.
    assert day2_first_day_high == pytest.approx(day2_first_actual_high)
    assert day2_first_day_high != day1_final_day_high


def test_relative_strength_added_only_when_nifty_df_provided(engine):
    df = build_two_day_ohlcv()
    result_without = engine.compute(df)
    assert "relative_strength" not in result_without.columns

    nifty_df = pd.DataFrame({"timestamp": df["timestamp"], "close": df["close"] * 10})  # arbitrary aligned series
    result_with = engine.compute(df, nifty_df=nifty_df)
    assert "relative_strength" in result_with.columns
