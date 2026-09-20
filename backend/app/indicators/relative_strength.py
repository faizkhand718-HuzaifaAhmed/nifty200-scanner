"""
Relative Strength vs NIFTY: rolling relative return (per explicit decision).

RS[t] = stock_close.pct_change(window)[t] - nifty_close.pct_change(window)[t]

The stock's percentage change over the trailing `window` bars, minus the
index's percentage change over the same trailing window, evaluated at
matching timestamps. Positive means the stock outperformed the index over
that window; negative means it underperformed. Both pct_change() calls
compare only the current bar to the bar `window` periods earlier - strictly
backward-looking.
"""
from __future__ import annotations

import pandas as pd


def relative_strength(stock_close: pd.Series, nifty_close: pd.Series, window: int = 20) -> pd.Series:
    """
    Precondition: `stock_close` and `nifty_close` must already be aligned -
    same length, same index, representing the same timestamps in the same
    order. This function does not merge/align them for you (that's a
    join-on-timestamp step the caller/engine performs first), since
    silently reindexing could hide missing-data problems you'd want to see.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    if len(stock_close) != len(nifty_close):
        raise ValueError("stock_close and nifty_close must be the same length (already aligned by timestamp)")

    stock_return = stock_close.pct_change(periods=window)
    nifty_return = nifty_close.pct_change(periods=window)
    return stock_return - nifty_return
