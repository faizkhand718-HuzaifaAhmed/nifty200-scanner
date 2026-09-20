"""
Shared Wilder recursive smoothing.

Wilder's original indicators (RSI, ATR, ADX) all use the same two-stage
smoothing: a simple average to seed the first value, then a recursive
average of the form avg[i] = (avg[i-1] * (period-1) + value[i]) / period.

This is implemented once here so RSI/ATR/ADX are guaranteed to bootstrap
identically, and so this specific piece of arithmetic has one dedicated
test rather than being re-verified indirectly through three different
indicators.

The recursion is strictly sequential (avg[i] depends only on avg[i-1] and
value[i]) - by construction it cannot use a future observation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """
    `series` may have a leading run of NaN values (e.g. from a prior
    .diff()/.shift()) but must have no NaNs *after* its first valid value -
    that's true of every series this is used on in this codebase (true
    range, gains/losses, +DM/-DM, DX).

    Returns a Series the same length/index as `series`. The first `period`
    valid values are consumed to seed the average (simple mean); output is
    NaN until then.
    """
    if period <= 0:
        raise ValueError("period must be positive")

    values = series.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)

    valid_positions = np.where(~np.isnan(values))[0]
    if len(valid_positions) < period:
        return pd.Series(out, index=series.index)

    start = valid_positions[0]
    seed_idx = start + period - 1
    if seed_idx >= n:
        return pd.Series(out, index=series.index)

    out[seed_idx] = values[start : start + period].mean()
    for i in range(seed_idx + 1, n):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period

    return pd.Series(out, index=series.index)
