"""
Volume-based indicators: VWAP (intraday, resets daily), average volume,
relative volume.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, session_date: pd.Series
) -> pd.Series:
    """
    Intraday volume-weighted average price, resetting at the start of each
    session (grouped by `session_date`). Cumulative sums within a group are
    causal: the value at bar i uses only bars <= i from the same day.
    """
    typical_price = (high + low + close) / 3
    pv = typical_price * volume
    cum_pv = pv.groupby(session_date).cumsum()
    cum_vol = volume.groupby(session_date).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def average_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling average volume over `window` periods, on whatever timeframe
    `volume` is already at (e.g. 20 daily bars, or 20 5-minute bars - the
    caller's choice, not this function's). This is NOT a same-time-of-day
    intraday seasonal average; that would need a separate calculation.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    return volume.rolling(window=window, min_periods=window).mean()


def relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Current bar's volume divided by the trailing average of the PRECEDING
    `window` bars (the current bar is excluded from its own baseline via
    `shift(1)`, so relative volume can meaningfully read above/below 1
    rather than being mechanically pulled toward 1 by including itself).
    """
    if window <= 0:
        raise ValueError("window must be positive")
    baseline = volume.shift(1).rolling(window=window, min_periods=window).mean()
    return volume / baseline.replace(0, np.nan)
