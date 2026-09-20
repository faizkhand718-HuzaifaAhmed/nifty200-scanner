"""
Retest condition: after a breakout/breakdown, price pulls back to test the
broken level before (implicitly) continuing - a trigger many intraday
traders wait for rather than chasing the initial breakout bar.

THIS IS A DESIGN DECISION, NOT A UNIQUELY "CORRECT" DEFINITION. Retest
patterns are defined many different ways in practice (touching the level
itself vs. a moving average, requiring a specific candle shape, requiring
volume to dry up on the pullback, etc.). As implemented here, a LONG
retest requires ALL of:
  1. a breakout occurred within the last `lookback_bars` bars (not
     counting the current bar itself, so a breakout bar never "retests
     itself" on the same candle)
  2. the current bar's low has come back within `tolerance_pct` of the
     broken resistance level
  3. the current bar's close has NOT decisively failed back through that
     level (still >= level * (1 - tolerance_pct))
SHORT is the mirror image using breakdown/support/high.

Review this specific definition before relying on it - it's the one piece
of this phase most likely to need adjustment to match your actual
trading rules.
"""
from __future__ import annotations

import pandas as pd


def retest_long(
    breakout: pd.Series,
    resistance: pd.Series,
    low: pd.Series,
    close: pd.Series,
    lookback_bars: int = 10,
    tolerance_pct: float = 0.003,
) -> pd.Series:
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")
    if tolerance_pct <= 0:
        raise ValueError("tolerance_pct must be positive")

    prior_breakout = breakout.fillna(False).astype(bool).shift(1, fill_value=False)
    recent_breakout = prior_breakout.rolling(window=lookback_bars, min_periods=1).max().astype(bool)

    near_level = (low - resistance).abs() / resistance <= tolerance_pct
    holding_above = close >= resistance * (1 - tolerance_pct)

    return recent_breakout & near_level.fillna(False) & holding_above.fillna(False) & resistance.notna()


def retest_short(
    breakdown: pd.Series,
    support: pd.Series,
    high: pd.Series,
    close: pd.Series,
    lookback_bars: int = 10,
    tolerance_pct: float = 0.003,
) -> pd.Series:
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")
    if tolerance_pct <= 0:
        raise ValueError("tolerance_pct must be positive")

    prior_breakdown = breakdown.fillna(False).astype(bool).shift(1, fill_value=False)
    recent_breakdown = prior_breakdown.rolling(window=lookback_bars, min_periods=1).max().astype(bool)

    near_level = (high - support).abs() / support <= tolerance_pct
    holding_below = close <= support * (1 + tolerance_pct)

    return recent_breakdown & near_level.fillna(False) & holding_below.fillna(False) & support.notna()
