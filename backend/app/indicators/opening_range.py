"""
Opening Range High/Low.

Per explicit decision: the opening range window is the first 30 minutes of
each session.

Design note: the window is measured from the FIRST bar present each day in
the input data, not from a hard-coded 09:15 market-open constant - this
module deliberately has no dependency on app.market_data (keeping the
indicators layer reusable/decoupled), and using "first bar of the day" as
the session start is both simpler and correctly handles a data feed that
happens to start later than 09:15 for some other reason. If you feed this
a series that already starts at 09:15 (the normal case), the result is the
standard 09:15-09:45 opening range.
"""
from __future__ import annotations

import pandas as pd


def opening_range_high_low(
    high: pd.Series,
    low: pd.Series,
    timestamp: pd.Series,
    session_date: pd.Series,
    window_minutes: int = 30,
) -> pd.DataFrame:
    """
    Returns columns ['opening_range_high', 'opening_range_low'].

    During the opening-range window itself, values reflect the running
    (still-forming) high/low of bars seen so far in the window - useful for
    a live dashboard. Once the window closes, the value is held constant
    for the rest of the session (forward-filled), since the opening range
    is a fixed reference level, not something that keeps expanding.
    """
    if window_minutes <= 0:
        raise ValueError("window_minutes must be positive")

    session_start = timestamp.groupby(session_date).transform("min")
    in_window = timestamp <= session_start + pd.Timedelta(minutes=window_minutes)

    windowed_high = high.where(in_window)
    windowed_low = low.where(in_window)

    running_high = windowed_high.groupby(session_date).cummax()
    running_low = windowed_low.groupby(session_date).cummin()

    or_high = running_high.groupby(session_date).ffill()
    or_low = running_low.groupby(session_date).ffill()

    return pd.DataFrame({"opening_range_high": or_high, "opening_range_low": or_low})
