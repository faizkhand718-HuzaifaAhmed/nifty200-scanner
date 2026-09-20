"""
Trend-strength indicator: ADX (Average Directional Index), Wilder's method.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._wilder import wilder_smooth
from app.indicators.volatility import true_range


def _directional_movement(high: pd.Series, low: pd.Series) -> tuple[pd.Series, pd.Series]:
    """+DM/-DM using only the current and PREVIOUS bar's high/low."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Preserve the leading NaN (no prior bar yet) rather than treating it
    # as "zero movement" - there's a difference between "no move" and
    # "we don't know yet".
    plus_dm[up_move.isna()] = np.nan
    minus_dm[down_move.isna()] = np.nan
    return plus_dm, minus_dm


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    """
    Returns columns ['plus_di', 'minus_di', 'adx']. Needs roughly
    2*period-1 bars before the first ADX value (one Wilder-smoothing pass
    to get +DI/-DI, a second to smooth DX into ADX) - that lag is expected,
    not a bug.
    """
    if period <= 0:
        raise ValueError("period must be positive")

    plus_dm, minus_dm = _directional_movement(high, low)
    tr = true_range(high, low, close)

    smoothed_plus_dm = wilder_smooth(plus_dm, period)
    smoothed_minus_dm = wilder_smooth(minus_dm, period)
    smoothed_tr = wilder_smooth(tr, period)

    plus_di = 100 * (smoothed_plus_dm / smoothed_tr)
    minus_di = 100 * (smoothed_minus_dm / smoothed_tr)

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum

    adx_line = wilder_smooth(dx, period)
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_line})
