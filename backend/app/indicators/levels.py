"""
Session-level price indicators: the current day's running high/low, and
the previous (completed) day's high/low held constant through today.
"""
from __future__ import annotations

import pandas as pd


def day_high_low(high: pd.Series, low: pd.Series, session_date: pd.Series) -> pd.DataFrame:
    """
    Running (expanding) high/low for the CURRENT session, using only bars
    up to and including the current one - this is the day-high/day-low as
    it would actually be observable in real time, not the eventual final
    high/low of the full day.
    """
    day_high = high.groupby(session_date).cummax()
    day_low = low.groupby(session_date).cummin()
    return pd.DataFrame({"day_high": day_high, "day_low": day_low})


def previous_day_high_low(high: pd.Series, low: pd.Series, session_date: pd.Series) -> pd.DataFrame:
    """
    The completed PREVIOUS trading day's high/low, held constant across
    every bar of the current day - this is the fixed reference level a
    trader would actually watch intraday, not a moving running value.
    NaN for the first day in the dataset (no prior day available).

    Precondition: rows must already be sorted ascending by timestamp so
    that `session_date`'s groupby order reflects chronological order.
    """
    daily_high = high.groupby(session_date).max()
    daily_low = low.groupby(session_date).min()

    prev_high_by_day = daily_high.shift(1)
    prev_low_by_day = daily_low.shift(1)

    prev_high = session_date.map(prev_high_by_day)
    prev_low = session_date.map(prev_low_by_day)
    return pd.DataFrame({"prev_day_high": prev_high, "prev_day_low": prev_low}, index=high.index)


def previous_day_close(close: pd.Series, session_date: pd.Series) -> pd.Series:
    """The completed previous trading day's closing price, held constant
    across every bar of the current day. NaN for the first day (no prior
    day). Same causality/ordering precondition as previous_day_high_low."""
    daily_close = close.groupby(session_date).last()
    prev_close_by_day = daily_close.shift(1)
    return session_date.map(prev_close_by_day)
