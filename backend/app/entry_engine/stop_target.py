"""
Stop-loss and target price calculation. Each is a pure function computing
ONE price given the entry price, direction, and already-computed
indicator values at the entry bar - called exactly once, at the moment
ENTRY_TRIGGER fires (see state_machine.py). Stops/targets are NOT
recomputed or trailed for the life of the position in this phase - a
fixed-at-entry stop/target is the simplest honest model; trailing stops
are a future enhancement, not implemented here.

Returns None (never a fabricated number) when the chosen method's
required input isn't available (e.g. SWING method with no confirmed
swing yet, or ATR method with a NaN ATR).
"""
from __future__ import annotations

from typing import Literal, Optional

import pandas as pd

from app.entry_engine.config import RISK_REWARD_MULTIPLES, EntryEngineConfig, StopMethod, TargetMethod

Direction = Literal["LONG", "SHORT"]


def _valid(x) -> bool:
    return x is not None and not pd.isna(x)


def compute_stop(
    method: StopMethod,
    entry_price: float,
    direction: Direction,
    ind_row: pd.Series,
    config: EntryEngineConfig,
    recent_swing_low: Optional[float] = None,
    recent_swing_high: Optional[float] = None,
) -> Optional[float]:
    if method == StopMethod.ATR:
        atr = ind_row.get("atr")
        if not _valid(atr):
            return None
        return entry_price - config.stop_atr_multiple * atr if direction == "LONG" else entry_price + config.stop_atr_multiple * atr

    if method == StopMethod.SWING:
        level = recent_swing_low if direction == "LONG" else recent_swing_high
        if not _valid(level):
            return None
        # A swing stop must sit on the correct side of entry (a swing low
        # above the LONG entry price, e.g. from a stale/irrelevant swing,
        # is not a usable stop).
        if direction == "LONG" and level >= entry_price:
            return None
        if direction == "SHORT" and level <= entry_price:
            return None
        return level

    if method == StopMethod.SUPPORT_RESISTANCE:
        level = ind_row.get("support") if direction == "LONG" else ind_row.get("resistance")
        if not _valid(level):
            return None
        if direction == "LONG" and level >= entry_price:
            return None
        if direction == "SHORT" and level <= entry_price:
            return None
        return level

    if method == StopMethod.PERCENTAGE:
        return entry_price * (1 - config.stop_percentage) if direction == "LONG" else entry_price * (1 + config.stop_percentage)

    raise ValueError(f"Unknown stop method: {method}")


def compute_target(
    method: TargetMethod,
    entry_price: float,
    stop_price: Optional[float],
    direction: Direction,
    ind_row: pd.Series,
    config: EntryEngineConfig,
) -> Optional[float]:
    if method in RISK_REWARD_MULTIPLES:
        if stop_price is None:
            return None
        risk = abs(entry_price - stop_price)
        if risk <= 0:
            return None
        multiple = RISK_REWARD_MULTIPLES[method]
        return entry_price + multiple * risk if direction == "LONG" else entry_price - multiple * risk

    if method == TargetMethod.ATR:
        atr = ind_row.get("atr")
        if not _valid(atr):
            return None
        return entry_price + config.target_atr_multiple * atr if direction == "LONG" else entry_price - config.target_atr_multiple * atr

    if method == TargetMethod.PREV_SUPPORT_RESISTANCE:
        if direction == "LONG":
            for level_key in ("r1", "r2", "r3"):
                level = ind_row.get(level_key)
                if _valid(level) and level > entry_price:
                    return level
        else:
            for level_key in ("s1", "s2", "s3"):
                level = ind_row.get(level_key)
                if _valid(level) and level < entry_price:
                    return level
        return None

    raise ValueError(f"Unknown target method: {method}")
