"""
Configurable thresholds for setup detection. Every numeric cutoff used by
the LONG/SHORT condition checks lives here, in one place, so tuning the
system never requires touching detection logic - only these values.

Defaults are reasonable starting points, not backtested "correct" values -
treat them as a first draft to tune once backtesting (a later phase) can
actually measure their effect.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SetupThresholds:
    # RSI zones: "bullish" momentum is RSI between rsi_bullish_min and
    # rsi_bullish_max (avoids chasing an already-extreme overbought read);
    # "bearish" is the mirrored zone for SHORT.
    rsi_bullish_min: float = 50.0
    rsi_bullish_max: float = 80.0
    rsi_bearish_min: float = 20.0
    rsi_bearish_max: float = 50.0

    # ADX: minimum trend strength required (direction-agnostic) before the
    # directional (+DI/-DI) confirmation is considered meaningful.
    adx_min: float = 20.0

    # Relative volume: current bar's volume must be at least this multiple
    # of its trailing average to count as "confirmed" by volume. Same
    # threshold used for both LONG and SHORT - see engine.py docstring on
    # why volume conditions aren't inverted.
    relative_volume_min: float = 1.2

    # Relative strength vs NIFTY: stock's rolling relative return must
    # exceed (LONG) or fall below the negative of (SHORT) this threshold.
    relative_strength_min: float = 0.0

    # Price-structure regime: require BOTH the most recent confirmed
    # high-swing AND low-swing to agree (classic Dow-theory uptrend/
    # downtrend definition) rather than either one alone.
    require_both_structure_swings: bool = True

    # Retest: how many bars back a breakout/breakdown may have occurred
    # and still count as "recently broken", and how close (as a fraction
    # of the level's price) the pullback must come to that level.
    retest_lookback_bars: int = 10
    retest_tolerance_pct: float = 0.003  # 0.3%
