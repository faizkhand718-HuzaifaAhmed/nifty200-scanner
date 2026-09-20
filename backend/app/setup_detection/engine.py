"""
SetupDetectionEngine: evaluates LONG and SHORT setup conditions per bar,
returning individual named boolean components rather than a single
TRUE/FALSE verdict - every signal stays explainable down to which specific
conditions did and didn't fire. Deliberately does NOT combine these into a
single 0-100 score or a pass/fail verdict - that's a later phase.

Input contract: `df` must be (or be shaped like) the output of
app.indicators.engine.IndicatorEngine.compute() for one stock - i.e. it
must already contain: timestamp, high, low, close, vwap, ema_9, ema_20,
ema_50, rsi, adx, plus_di, minus_di, volume, average_volume,
relative_volume, breakout, breakdown, support, resistance, higher_high,
lower_high, higher_low, lower_low. `relative_strength` is optional (only
present if that engine run was given a nifty_df) - its two conditions are
simply omitted if absent, never fabricated.

`nifty_df`, if given, must be NIFTY's OWN IndicatorEngine.compute() output
(supplying nifty ema_20/ema_50 for the market-direction condition) - pass
None to skip market_confirmation entirely.

Note on Volume / Relative Volume: these measure conviction/participation,
not direction - a big volume spike matters the same way whether you're
considering a long or a short. They are therefore NOT inverted between
LONG and SHORT (unlike every other condition here); this is a deliberate
choice, not an oversight.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from app.setup_detection import conditions as cond
from app.setup_detection.config import SetupThresholds
from app.setup_detection.price_structure import (
    price_structure_bearish,
    price_structure_bullish,
    price_structure_regime,
)
from app.setup_detection.retest import retest_long, retest_short

REQUIRED_COLUMNS = {
    "timestamp", "high", "low", "close", "vwap", "ema_9", "ema_20", "ema_50",
    "rsi", "adx", "plus_di", "minus_di", "volume", "average_volume", "relative_volume",
    "breakout", "breakdown", "support", "resistance",
    "higher_high", "lower_high", "higher_low", "lower_low",
}


class SetupDetectionEngine:
    def __init__(self, thresholds: Optional[SetupThresholds] = None):
        self.thresholds = thresholds or SetupThresholds()

    def compute(self, df: pd.DataFrame, nifty_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")

        t = self.thresholds
        out = pd.DataFrame(index=df.index)
        out["timestamp"] = df["timestamp"]

        regime = price_structure_regime(df["higher_high"], df["lower_high"], df["higher_low"], df["lower_low"])

        # --- LONG components ---
        out["long_above_vwap"] = cond.above_vwap(df["close"], df["vwap"])
        out["long_ema9_above_ema20"] = cond.ema_bullish_alignment(df["ema_9"], df["ema_20"])
        out["long_ema20_above_ema50"] = cond.ema_bullish_alignment(df["ema_20"], df["ema_50"])
        out["long_price_structure"] = price_structure_bullish(regime, t.require_both_structure_swings)
        out["long_volume_confirmation"] = cond.volume_above_average(df["volume"], df["average_volume"])
        out["long_relative_volume"] = cond.relative_volume_confirmed(df["relative_volume"], t.relative_volume_min)
        out["long_rsi"] = cond.rsi_in_zone(df["rsi"], t.rsi_bullish_min, t.rsi_bullish_max)
        out["long_adx_trend"] = cond.adx_bullish(df["adx"], df["plus_di"], df["minus_di"], t.adx_min)
        out["long_breakout"] = df["breakout"].fillna(False).astype(bool)
        out["long_retest"] = retest_long(
            df["breakout"], df["resistance"], df["low"], df["close"], t.retest_lookback_bars, t.retest_tolerance_pct
        )

        # --- SHORT components ---
        out["short_below_vwap"] = cond.below_vwap(df["close"], df["vwap"])
        out["short_ema9_below_ema20"] = cond.ema_bearish_alignment(df["ema_9"], df["ema_20"])
        out["short_ema20_below_ema50"] = cond.ema_bearish_alignment(df["ema_20"], df["ema_50"])
        out["short_price_structure"] = price_structure_bearish(regime, t.require_both_structure_swings)
        out["short_volume_confirmation"] = out["long_volume_confirmation"]  # not directional, see docstring
        out["short_relative_volume"] = out["long_relative_volume"]  # not directional, see docstring
        out["short_rsi"] = cond.rsi_in_zone(df["rsi"], t.rsi_bearish_min, t.rsi_bearish_max)
        out["short_adx_trend"] = cond.adx_bearish(df["adx"], df["plus_di"], df["minus_di"], t.adx_min)
        out["short_breakdown"] = df["breakdown"].fillna(False).astype(bool)
        out["short_retest"] = retest_short(
            df["breakdown"], df["support"], df["high"], df["close"], t.retest_lookback_bars, t.retest_tolerance_pct
        )

        if "relative_strength" in df.columns:
            out["long_relative_strength"] = cond.relative_strength_bullish(
                df["relative_strength"], t.relative_strength_min
            )
            out["short_relative_strength"] = cond.relative_strength_bearish(
                df["relative_strength"], t.relative_strength_min
            )

        if nifty_df is not None:
            nifty_aligned = df[["timestamp"]].merge(
                nifty_df[["timestamp", "ema_20", "ema_50"]].rename(
                    columns={"ema_20": "nifty_ema_20", "ema_50": "nifty_ema_50"}
                ),
                on="timestamp",
                how="left",
            )
            out["long_market_confirmation"] = cond.market_direction_bullish(
                nifty_aligned["nifty_ema_20"], nifty_aligned["nifty_ema_50"]
            )
            out["short_market_confirmation"] = cond.market_direction_bearish(
                nifty_aligned["nifty_ema_20"], nifty_aligned["nifty_ema_50"]
            )

        return out

    @staticmethod
    def latest_components(result: pd.DataFrame) -> dict:
        """
        Returns the most recent row's components as {"long": {...},
        "short": {...}} - matching the flat-dict shape from the phase
        spec, split by side since both LONG and SHORT are evaluated
        simultaneously on every bar (the engine reports what's true, it
        doesn't assert the two sides are mutually exclusive).
        NaN/<NA> components (e.g. relative_strength or market_confirmation
        when their inputs weren't supplied) are omitted rather than
        reported as False.
        """
        last = result.iloc[-1]
        long_components = {
            c[len("long_") :]: bool(v) for c, v in last.items() if c.startswith("long_") and not pd.isna(v)
        }
        short_components = {
            c[len("short_") :]: bool(v) for c, v in last.items() if c.startswith("short_") and not pd.isna(v)
        }
        return {"long": long_components, "short": short_components}
