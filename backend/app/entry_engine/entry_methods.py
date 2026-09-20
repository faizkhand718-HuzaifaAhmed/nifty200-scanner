"""
Entry-trigger detection. Each method here is a pure function of the
CURRENT and PREVIOUS bar's already-computed indicator/setup values -
nothing here reads a future bar, and nothing here reads or is even aware
of the Opportunity Score. That second point is deliberate and load-
bearing: see tests/test_entry_engine_no_score_dependency.py, which
inspects this package's imports and fails if app.scoring is ever
referenced here.

Each function returns (approaching, triggered):
  - triggered: the exact entry condition fired on this bar.
  - approaching: price/indicators are within a configured tolerance of
    triggering, but haven't yet - this is what promotes SETUP to
    CONFIRMATION. This "approaching" band is a judgment call (see
    EntryEngineConfig.approach_tolerance_pct), not a standard definition.

All values are read defensively (NaN/missing -> no signal), never
fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

import pandas as pd

from app.entry_engine.config import EntryEngineConfig

Direction = Literal["LONG", "SHORT"]


@dataclass
class BarContext:
    ind: pd.Series
    prev_ind: Optional[pd.Series]
    setup: pd.Series
    direction: Direction


def _valid(x) -> bool:
    return x is not None and not pd.isna(x)


def _within_pct(higher: float, lower: float, tolerance_pct: float) -> bool:
    """True if `lower` is within `tolerance_pct` of `higher`, approaching
    from below (higher > lower)."""
    if higher <= 0:
        return False
    return (higher - lower) / higher <= tolerance_pct


def breakout(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """LONG only: close crosses above resistance (Phase 4's pivot R1)."""
    triggered = bool(ctx.setup.get("long_breakout", False))
    resistance = ctx.ind.get("resistance")
    approaching = (
        not triggered
        and _valid(resistance)
        and ctx.ind["close"] < resistance
        and _within_pct(resistance, ctx.ind["close"], config.approach_tolerance_pct)
    )
    return bool(approaching), bool(triggered)


def breakdown(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """SHORT only: close crosses below support (Phase 4's pivot S1)."""
    triggered = bool(ctx.setup.get("short_breakdown", False))
    support = ctx.ind.get("support")
    approaching = (
        not triggered
        and _valid(support)
        and ctx.ind["close"] > support
        and _within_pct(ctx.ind["close"], support, config.approach_tolerance_pct)
    )
    return bool(approaching), bool(triggered)


def vwap_reclaim(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """LONG only: close crosses from below VWAP to above it."""
    if ctx.prev_ind is None:
        return False, False
    vwap, prev_vwap = ctx.ind.get("vwap"), ctx.prev_ind.get("vwap")
    if not _valid(vwap) or not _valid(prev_vwap):
        return False, False
    triggered = ctx.prev_ind["close"] < prev_vwap and ctx.ind["close"] > vwap
    approaching = (
        not triggered and ctx.ind["close"] < vwap and _within_pct(vwap, ctx.ind["close"], config.approach_tolerance_pct)
    )
    return bool(approaching), bool(triggered)


def vwap_rejection(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """SHORT only: close crosses from above VWAP to below it."""
    if ctx.prev_ind is None:
        return False, False
    vwap, prev_vwap = ctx.ind.get("vwap"), ctx.prev_ind.get("vwap")
    if not _valid(vwap) or not _valid(prev_vwap):
        return False, False
    triggered = ctx.prev_ind["close"] > prev_vwap and ctx.ind["close"] < vwap
    approaching = (
        not triggered and ctx.ind["close"] > vwap and _within_pct(ctx.ind["close"], vwap, config.approach_tolerance_pct)
    )
    return bool(approaching), bool(triggered)


def ema_confirmation(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """Either direction: EMA9 crosses to the favorable side of EMA20 AND
    price is on that same side."""
    ema9, ema20 = ctx.ind.get("ema_9"), ctx.ind.get("ema_20")
    if not _valid(ema9) or not _valid(ema20):
        return False, False
    if ctx.direction == "LONG":
        triggered = ema9 > ema20 and ctx.ind["close"] > ema20
        approaching = (
            not triggered and ema9 <= ema20 and _within_pct(ema20, ema9, config.ema_convergence_tolerance_pct)
        )
    else:
        triggered = ema9 < ema20 and ctx.ind["close"] < ema20
        approaching = (
            not triggered and ema9 >= ema20 and _within_pct(ema9, ema20, config.ema_convergence_tolerance_pct)
        )
    return bool(approaching), bool(triggered)


def opening_range_breakout(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """Either direction: close breaks the opening range high/low (Phase 4)."""
    if ctx.direction == "LONG":
        level = ctx.ind.get("opening_range_high")
        if not _valid(level):
            return False, False
        triggered = ctx.ind["close"] > level
        approaching = not triggered and _within_pct(level, ctx.ind["close"], config.approach_tolerance_pct)
    else:
        level = ctx.ind.get("opening_range_low")
        if not _valid(level):
            return False, False
        triggered = ctx.ind["close"] < level
        approaching = not triggered and _within_pct(ctx.ind["close"], level, config.approach_tolerance_pct)
    return bool(approaching), bool(triggered)


def retest(ctx: BarContext, config: EntryEngineConfig) -> Tuple[bool, bool]:
    """Either direction: Phase 5's retest condition fires. "Approaching"
    here means a breakout/breakdown already happened and we're watching
    for the pullback - there's no separate proximity check since Phase 5's
    retest() already encodes proximity to the level."""
    if ctx.direction == "LONG":
        triggered = bool(ctx.setup.get("long_retest", False))
        approaching = (not triggered) and bool(ctx.setup.get("long_breakout", False))
    else:
        triggered = bool(ctx.setup.get("short_retest", False))
        approaching = (not triggered) and bool(ctx.setup.get("short_breakdown", False))
    return bool(approaching), bool(triggered)


ENTRY_METHOD_FUNCTIONS = {
    "breakout": breakout,
    "breakdown": breakdown,
    "vwap_reclaim": vwap_reclaim,
    "vwap_rejection": vwap_rejection,
    "ema_confirmation": ema_confirmation,
    "opening_range_breakout": opening_range_breakout,
    "retest": retest,
}
