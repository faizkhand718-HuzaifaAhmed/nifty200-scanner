"""
Configuration for the Entry/Risk/Reward engine: which entry trigger, stop-
loss, and target method to use, plus every numeric threshold those methods
need. None of these defaults are backtested "correct" values - they are a
first draft to be tuned once backtesting (a later phase) can measure their
actual effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntryMethod(str, Enum):
    BREAKOUT = "breakout"                        # LONG only
    BREAKDOWN = "breakdown"                       # SHORT only
    VWAP_RECLAIM = "vwap_reclaim"                 # LONG only
    VWAP_REJECTION = "vwap_rejection"             # SHORT only
    EMA_CONFIRMATION = "ema_confirmation"         # either direction
    OPENING_RANGE_BREAKOUT = "opening_range_breakout"  # either direction
    RETEST = "retest"                             # either direction


# Which direction(s) each entry method is valid for - enforced at
# TradeLifecycle construction time, not silently allowed.
ENTRY_METHOD_ALLOWED_DIRECTIONS = {
    EntryMethod.BREAKOUT: {"LONG"},
    EntryMethod.BREAKDOWN: {"SHORT"},
    EntryMethod.VWAP_RECLAIM: {"LONG"},
    EntryMethod.VWAP_REJECTION: {"SHORT"},
    EntryMethod.EMA_CONFIRMATION: {"LONG", "SHORT"},
    EntryMethod.OPENING_RANGE_BREAKOUT: {"LONG", "SHORT"},
    EntryMethod.RETEST: {"LONG", "SHORT"},
}


class StopMethod(str, Enum):
    ATR = "atr"
    SWING = "swing"
    SUPPORT_RESISTANCE = "support_resistance"
    PERCENTAGE = "percentage"


class TargetMethod(str, Enum):
    RISK_REWARD_1_5 = "risk_reward_1_5"
    RISK_REWARD_2 = "risk_reward_2"
    RISK_REWARD_3 = "risk_reward_3"
    ATR = "atr"
    PREV_SUPPORT_RESISTANCE = "prev_support_resistance"


RISK_REWARD_MULTIPLES = {
    TargetMethod.RISK_REWARD_1_5: 1.5,
    TargetMethod.RISK_REWARD_2: 2.0,
    TargetMethod.RISK_REWARD_3: 3.0,
}


@dataclass
class EntryEngineConfig:
    entry_method: EntryMethod = EntryMethod.BREAKOUT
    stop_method: StopMethod = StopMethod.SUPPORT_RESISTANCE
    target_method: TargetMethod = TargetMethod.RISK_REWARD_2

    # How close price must be to a trigger level (as a fraction of price)
    # to count as CONFIRMATION rather than plain SETUP.
    approach_tolerance_pct: float = 0.003  # 0.3%

    # How close EMA9 must be to EMA20 (as a fraction of EMA20) to count as
    # "converging" for the EMA_CONFIRMATION method's CONFIRMATION state.
    ema_convergence_tolerance_pct: float = 0.002  # 0.2%

    # Stop-loss method parameters.
    stop_atr_multiple: float = 1.5
    stop_percentage: float = 0.005  # 0.5%

    # Target method parameters.
    target_atr_multiple: float = 3.0

    # A setup that never triggers within this many bars is INVALIDATED
    # (stale), rather than tracked forever.
    max_bars_without_trigger: int = 40
