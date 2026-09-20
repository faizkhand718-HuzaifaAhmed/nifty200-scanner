"""
Same proof technique as Phase 4's test_no_lookahead.py, one layer up: for
every LONG/SHORT component, the value at a given timestamp must be
identical whether that timestamp is the last row of a shorter dataset or
somewhere in the middle of a longer one. Both the stock's and NIFTY's
IndicatorEngine outputs are recomputed on each prefix (mirroring how this
would actually run live, one bar at a time), not just the setup engine
in isolation.
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
from app.setup_detection.engine import SetupDetectionEngine  # noqa: E402

HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"
DAYS = [date(2026, 1, 27), date(2026, 1, 28), date(2026, 1, 29)]


def build_ohlcv(days, seed_price) -> pd.DataFrame:
    calendar = NSECalendar.from_file(HOLIDAY_FILE)
    timestamps = []
    for d in days:
        timestamps.extend(calendar.session_timestamps(d, Timeframe.FIFTEEN_MIN))
    rows = []
    price = seed_price
    for i, ts in enumerate(timestamps):
        price += ((-1) ** i) * (0.3 + (i % 7) * 0.05)
        c = round(price, 2)
        rows.append((ts, c - 0.1, c + 0.4, c - 0.4, c, 500 + (i * 13) % 400))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


@pytest.fixture(scope="module")
def full_setup_result():
    stock_ohlcv = build_ohlcv(DAYS, seed_price=250.0)
    nifty_ohlcv = build_ohlcv(DAYS, seed_price=20000.0)
    stock_ind = IndicatorEngine().compute(stock_ohlcv)
    nifty_ind = IndicatorEngine().compute(nifty_ohlcv)
    result = SetupDetectionEngine().compute(stock_ind, nifty_df=nifty_ind)
    return stock_ohlcv, nifty_ohlcv, result


@pytest.mark.parametrize("cutoff_fraction", [0.4, 0.6, 0.85])
def test_setup_components_unchanged_by_future_rows(full_setup_result, cutoff_fraction):
    stock_ohlcv, nifty_ohlcv, full_result = full_setup_result
    cutoff = max(20, int(len(stock_ohlcv) * cutoff_fraction))

    prefix_stock_ind = IndicatorEngine().compute(stock_ohlcv.iloc[:cutoff].copy())
    prefix_nifty_ind = IndicatorEngine().compute(nifty_ohlcv.iloc[:cutoff].copy())
    prefix_result = SetupDetectionEngine().compute(prefix_stock_ind, nifty_df=prefix_nifty_ind)

    last_prefix = prefix_result.iloc[-1]
    last_full = full_result.iloc[cutoff - 1]
    assert last_prefix["timestamp"] == last_full["timestamp"]

    component_cols = [c for c in full_result.columns if c.startswith("long_") or c.startswith("short_")]
    for col in component_cols:
        a, b = last_prefix[col], last_full[col]
        if pd.isna(a) and pd.isna(b):
            continue
        assert bool(a) == bool(b), (
            f"Component '{col}' at cutoff={cutoff} changed when future rows "
            f"were appended: prefix-only={a!r} vs full-dataset={b!r}."
        )
