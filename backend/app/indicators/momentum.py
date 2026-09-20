"""
Momentum indicator: RSI, Wilder's original formulation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._wilder import wilder_smooth


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI. `close.diff()` looks at the current and PREVIOUS bar only
    (never forward); the Wilder smoothing of gains/losses is likewise
    strictly sequential. The first `period` values are NaN - callers must
    treat NaN as "not enough history yet", never fabricate a value for it.
    """
    if period <= 0:
        raise ValueError("period must be positive")

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = wilder_smooth(gains, period)
    avg_loss = wilder_smooth(losses, period)

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    # All-gains-no-losses over the window is a defined edge case: RSI = 100.
    result = result.where(avg_loss != 0, 100.0)
    result[avg_gain.isna()] = np.nan
    return result
