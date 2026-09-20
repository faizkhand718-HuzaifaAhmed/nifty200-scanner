"""
The 7 trade-lifecycle states this engine tracks per (symbol, direction).
"""
from __future__ import annotations

from enum import Enum


class TradeState(str, Enum):
    SETUP = "SETUP"
    CONFIRMATION = "CONFIRMATION"
    ENTRY_TRIGGER = "ENTRY_TRIGGER"
    POSITION_ACTIVE = "POSITION_ACTIVE"
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    INVALIDATED = "INVALIDATED"


TERMINAL_STATES = {TradeState.TARGET_HIT, TradeState.STOP_LOSS_HIT, TradeState.INVALIDATED}
