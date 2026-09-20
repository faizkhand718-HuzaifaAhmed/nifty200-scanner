"""
Trend indicators: EMA family and MACD.

Both are built on pandas' `.ewm(..., adjust=False)`, which is a pure
recursive filter - value[i] depends only on value[i-1] and the current
input, never on future rows. That is the mechanical no-look-ahead
guarantee for these two indicators.
"""
from __future__ import annotations

import pandas as pd


def ema(close: pd.Series, span: int) -> pd.Series:
    """Exponential moving average of `close` with the given span."""
    if span <= 0:
        raise ValueError("span must be positive")
    return close.ewm(span=span, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    Standard MACD. Returns columns ['macd', 'signal', 'histogram'].

    Note: the 12/26/9 periods here are MACD's own internal convention and
    are independent of the standalone EMA 9/20/50/200 indicators computed
    elsewhere in this engine.
    """
    if fast >= slow:
        raise ValueError("fast period must be less than slow period")
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})
