"""
Support/Resistance via classic floor-trader pivot points, and the
Breakout/Breakdown flags derived from them (per explicit decision).

All levels are computed from the PREVIOUS trading day's completed high,
low, and close, and held constant through the current session - this is
the standard floor-trader pivot convention and is fully causal: nothing
here ever reads the current (still-forming) day's high/low/close to
determine today's levels.
"""
from __future__ import annotations

import pandas as pd

from app.indicators.levels import previous_day_close, previous_day_high_low


def classic_pivot_points(prev_high: pd.Series, prev_low: pd.Series, prev_close: pd.Series) -> pd.DataFrame:
    """
    Standard floor-trader pivot formulas:
        PP = (H + L + C) / 3
        R1 = 2*PP - L        S1 = 2*PP - H
        R2 = PP + (H - L)    S2 = PP - (H - L)
        R3 = H + 2*(PP - L)  S3 = L - 2*(H - PP)
    where H, L, C are the previous day's high, low, close.
    """
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high
    r2 = pivot + (prev_high - prev_low)
    s2 = pivot - (prev_high - prev_low)
    r3 = prev_high + 2 * (pivot - prev_low)
    s3 = prev_low - 2 * (prev_high - pivot)
    return pd.DataFrame(
        {"pivot": pivot, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}
    )


def support_resistance(
    high: pd.Series, low: pd.Series, close: pd.Series, session_date: pd.Series
) -> pd.DataFrame:
    """
    Returns columns: pivot, r1, r2, r3, s1, s2, s3, support, resistance,
    breakout, breakdown.

    `support` = S1 and `resistance` = R1 (the nearest pivot levels) are
    exposed as the headline single Support/Resistance values you asked
    for; the full ladder (R2/R3/S2/S3) is included too since it's the
    standard, complete floor-trader method and costs nothing extra to
    expose for transparency.

    `breakout` = current bar's close > resistance (R1).
    `breakdown` = current bar's close < support (S1).
    Both are plain boolean flags per bar, not "first crossing only" - if
    you want a one-shot transition signal instead, diff() this yourself.
    All NaN for the first day (no previous day to derive levels from).
    """
    prev_hl = previous_day_high_low(high, low, session_date)
    prev_c = previous_day_close(close, session_date)

    pivots = classic_pivot_points(prev_hl["prev_day_high"], prev_hl["prev_day_low"], prev_c)
    pivots.index = high.index

    result = pivots.copy()
    result["support"] = pivots["s1"]
    result["resistance"] = pivots["r1"]
    # Nullable boolean dtype so True/False/<NA> (unknown, no level yet) can
    # all coexist in one column - a plain bool dtype can't hold NA.
    result["breakout"] = (close > pivots["r1"]).astype("boolean")
    result["breakdown"] = (close < pivots["s1"]).astype("boolean")
    # Where levels are undefined (first day), breakout/breakdown must also
    # be "unknown", not False - False would misleadingly assert "no
    # breakout happened" when we simply have no reference level yet.
    result.loc[pivots["r1"].isna(), "breakout"] = pd.NA
    result.loc[pivots["s1"].isna(), "breakdown"] = pd.NA
    return result
