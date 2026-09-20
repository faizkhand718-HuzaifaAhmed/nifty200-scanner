"""
Volatility indicator: Average True Range (ATR), Wilder's method.
"""
from __future__ import annotations

import pandas as pd

from app.indicators._wilder import wilder_smooth


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range using the PREVIOUS bar's close (`close.shift(1)`, strictly
    backward-looking) alongside the current bar's own high/low."""
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed ATR. NaN for the first `period` values."""
    if period <= 0:
        raise ValueError("period must be positive")
    tr = true_range(high, low, close)
    return wilder_smooth(tr, period)
