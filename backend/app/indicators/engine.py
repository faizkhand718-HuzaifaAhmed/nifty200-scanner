"""
IndicatorEngine: computes the full available indicator set on a single,
already-cleaned OHLCV DataFrame for one symbol.

Contract this engine relies on: the caller passes ONLY candles up to and
including the point in time indicators are wanted for - this engine never
receives, and has no mechanism to request, future data. Every function it
calls (see trend.py, momentum.py, volatility.py, trend_strength.py,
volume.py, levels.py, opening_range.py, pivots.py, structure.py,
relative_strength.py) is built from pandas rolling/ewm/expanding/
cumulative operations, which by construction only read backward. See
tests/test_no_lookahead.py for a proof: appending future rows never
changes an already-computed value at an earlier timestamp.

Trading-rule decisions confirmed by the user for the indicators below:
  - Opening Range: first 30 minutes of the session.
  - Support/Resistance: classic floor-trader pivot points from the
    previous day's H/L/C (support=S1, resistance=R1; full ladder exposed).
  - Breakout/Breakdown: close crosses above R1 / below S1.
  - Relative Strength vs NIFTY: rolling relative return (stock % change
    minus NIFTY % change over the same trailing window).
  - Higher/Lower High/Low: 2-bar fractal swing confirmation (n=2) - this
    specific lookback (n) was not part of what was asked/confirmed and is
    a reasonable, easily-adjustable default; flag if you want it changed.
"""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd

from app.indicators.levels import day_high_low, previous_day_close, previous_day_high_low
from app.indicators.momentum import rsi
from app.indicators.opening_range import opening_range_high_low
from app.indicators.pivots import support_resistance
from app.indicators.relative_strength import relative_strength
from app.indicators.structure import market_structure
from app.indicators.trend import ema, macd
from app.indicators.trend_strength import adx
from app.indicators.volatility import atr
from app.indicators.volume import average_volume, relative_volume, vwap

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


class IndicatorEngine:
    def __init__(
        self,
        ema_spans: Sequence[int] = (9, 20, 50, 200),
        rsi_period: int = 14,
        atr_period: int = 14,
        adx_period: int = 14,
        volume_window: int = 20,
        opening_range_minutes: int = 30,
        swing_lookback: int = 2,
        relative_strength_window: int = 20,
    ):
        self.ema_spans = tuple(ema_spans)
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.adx_period = adx_period
        self.volume_window = volume_window
        self.opening_range_minutes = opening_range_minutes
        self.swing_lookback = swing_lookback
        self.relative_strength_window = relative_strength_window

    def compute(self, df: pd.DataFrame, nifty_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        `nifty_df`, if given, must have columns ['timestamp', 'close'] and
        is left-joined onto `df` by timestamp to compute Relative Strength.
        If omitted, the relative_strength column is simply not added
        (never fabricated from a missing index series).
        """
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")
        if len(df) > 1 and not df["timestamp"].is_monotonic_increasing:
            raise ValueError(
                "candles must be sorted ascending by timestamp - every "
                "rolling/expanding/ewm calculation here assumes row order "
                "reflects time order in order to be causal"
            )

        out = df.reset_index(drop=True).copy()
        session_date = out["timestamp"].dt.date

        for span in self.ema_spans:
            out[f"ema_{span}"] = ema(out["close"], span)

        macd_df = macd(out["close"])
        out["macd"] = macd_df["macd"]
        out["macd_signal"] = macd_df["signal"]
        out["macd_histogram"] = macd_df["histogram"]

        out["rsi"] = rsi(out["close"], self.rsi_period)
        out["atr"] = atr(out["high"], out["low"], out["close"], self.atr_period)

        adx_df = adx(out["high"], out["low"], out["close"], self.adx_period)
        out["plus_di"] = adx_df["plus_di"]
        out["minus_di"] = adx_df["minus_di"]
        out["adx"] = adx_df["adx"]

        out["vwap"] = vwap(out["high"], out["low"], out["close"], out["volume"], session_date)
        out["average_volume"] = average_volume(out["volume"], self.volume_window)
        out["relative_volume"] = relative_volume(out["volume"], self.volume_window)

        dh_dl = day_high_low(out["high"], out["low"], session_date)
        out["day_high"] = dh_dl["day_high"]
        out["day_low"] = dh_dl["day_low"]

        prev = previous_day_high_low(out["high"], out["low"], session_date)
        out["prev_day_high"] = prev["prev_day_high"]
        out["prev_day_low"] = prev["prev_day_low"]
        out["prev_day_close"] = previous_day_close(out["close"], session_date)

        orange = opening_range_high_low(
            out["high"], out["low"], out["timestamp"], session_date, self.opening_range_minutes
        )
        out["opening_range_high"] = orange["opening_range_high"]
        out["opening_range_low"] = orange["opening_range_low"]

        sr = support_resistance(out["high"], out["low"], out["close"], session_date)
        for col in ("pivot", "r1", "r2", "r3", "s1", "s2", "s3", "support", "resistance", "breakout", "breakdown"):
            out[col] = sr[col]

        structure = market_structure(out["high"], out["low"], self.swing_lookback)
        for col in structure.columns:
            out[col] = structure[col]

        if nifty_df is not None:
            nifty_aligned = out[["timestamp"]].merge(
                nifty_df[["timestamp", "close"]].rename(columns={"close": "nifty_close"}),
                on="timestamp",
                how="left",
            )
            out["relative_strength"] = relative_strength(
                out["close"], nifty_aligned["nifty_close"], self.relative_strength_window
            )

        return out

