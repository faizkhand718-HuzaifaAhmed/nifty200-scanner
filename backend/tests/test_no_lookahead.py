"""
This is the actual proof of "no look-ahead bias" for the indicator engine,
not just an assertion in a docstring: for every indicator column, the value
computed at a given timestamp must be IDENTICAL whether that timestamp is
the last row in the dataset or somewhere in the middle of a longer dataset.
If appending future rows ever changed a past value, some calculation would
be reading data it shouldn't have access to.
"""
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
DAY3 = date(2026, 1, 29)


def build_three_day_ohlcv() -> pd.DataFrame:
    calendar = NSECalendar.from_file(HOLIDAY_FILE)
    timestamps = (
        calendar.session_timestamps(DAY1, Timeframe.FIFTEEN_MIN)
        + calendar.session_timestamps(DAY2, Timeframe.FIFTEEN_MIN)
        + calendar.session_timestamps(DAY3, Timeframe.FIFTEEN_MIN)
    )
    rows = []
    price = 250.0
    for i, ts in enumerate(timestamps):
        # A deliberately jagged deterministic pattern (not just a smooth
        # trend) so rolling/EWM calculations have something non-trivial to
        # chew on.
        price += ((-1) ** i) * (0.3 + (i % 7) * 0.05)
        close = round(price, 2)
        high = close + 0.4
        low = close - 0.4
        open_ = close - 0.1
        volume = 500 + (i * 13) % 400
        rows.append((ts, open_, high, low, close, volume))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


INDICATOR_COLUMNS = [
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
]


@pytest.fixture(scope="module")
def full_result():
    engine = IndicatorEngine()
    df = build_three_day_ohlcv()
    return df, engine.compute(df)


@pytest.mark.parametrize("cutoff_fraction", [0.3, 0.5, 0.7, 0.9])
def test_past_values_unchanged_by_future_rows(full_result, cutoff_fraction):
    df, full_computed = full_result
    engine = IndicatorEngine()

    cutoff = max(10, int(len(df) * cutoff_fraction))  # ensure enough history for warm-up
    prefix_df = df.iloc[:cutoff].copy()
    prefix_computed = engine.compute(prefix_df)

    last_row_prefix = prefix_computed.iloc[-1]
    last_row_full = full_computed.iloc[cutoff - 1]

    assert last_row_prefix["timestamp"] == last_row_full["timestamp"]

    for col in INDICATOR_COLUMNS:
        a, b = last_row_prefix[col], last_row_full[col]
        if pd.isna(a) and pd.isna(b):
            continue
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), (
            f"Column '{col}' at cutoff={cutoff} changed when future rows "
            f"were appended: prefix-only={a!r} vs full-dataset={b!r}. This "
            f"indicates a look-ahead bug."
        )


def test_every_indicator_column_is_exercised_by_the_lookahead_check():
    """Guards against silently forgetting to add a new indicator to
    INDICATOR_COLUMNS above when the engine grows."""
    engine = IndicatorEngine()
    df = build_three_day_ohlcv()
    result = engine.compute(df)
    non_input_columns = set(result.columns) - {"timestamp", "open", "high", "low", "close", "volume"}
    assert non_input_columns == set(INDICATOR_COLUMNS)
