"""
Daily-timeframe indicators that were never part of Phase 4's original set
(which was built for the intraday scanner: VWAP, opening range, session
pivots). 52-week high/low and simple period returns are inherently
daily/swing concepts, not intraday ones - this is genuinely new,
additive functionality, not a duplicate of anything in app/indicators/.

Every function here is causal by construction (pandas .rolling() only
looks backward) and every function is a pure, timeframe-agnostic
DataFrame transform - no I/O, no NSE-specific knowledge, fully testable
with synthetic data.
"""
from __future__ import annotations

import pandas as pd


def fifty_two_week_high_low(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 252) -> pd.DataFrame:
    """window=252 trading days is the standard approximation of a
    calendar year of NSE trading sessions. Requires at least `window`
    rows of history to produce a non-NaN value for the earliest rows -
    callers should treat NaN as "insufficient data," never impute it."""
    rolling_high = high.rolling(window=window, min_periods=window).max()
    rolling_low = low.rolling(window=window, min_periods=window).min()
    pct_from_high = (close - rolling_high) / rolling_high * 100
    pct_from_low = (close - rolling_low) / rolling_low * 100
    return pd.DataFrame({
        "fifty_two_week_high": rolling_high,
        "fifty_two_week_low": rolling_low,
        "pct_from_52w_high": pct_from_high,
        "pct_from_52w_low": pct_from_low,
    })


def period_return_pct(close: pd.Series, periods: int) -> pd.Series:
    """Simple (not annualized) percentage return over the trailing
    `periods` bars - close today vs close `periods` bars ago."""
    if periods <= 0:
        raise ValueError("periods must be positive")
    return close.pct_change(periods=periods) * 100


def daily_relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """Today's volume as a multiple of the trailing `window`-day AVERAGE
    volume, EXCLUDING today's own bar from that average (same
    no-self-reference principle Phase 4's intraday relative_volume
    follows) - a rolling mean shifted by one bar."""
    if window <= 0:
        raise ValueError("window must be positive")
    baseline = volume.shift(1).rolling(window=window, min_periods=window).mean()
    return volume / baseline
