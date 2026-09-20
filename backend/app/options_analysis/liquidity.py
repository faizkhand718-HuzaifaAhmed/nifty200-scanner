"""
Liquidity assessment. "Prefer liquid contracts with acceptable spread,
volume, and open interest" / "do NOT select an option simply because the
premium is cheap" - this module is where that rule lives: liquidity is a
GATE (passes_liquidity_filter), not a score that a low premium can offset.
See contract_selection.py for how the gate is actually applied during
selection.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from app.options_analysis.config import OptionSelectionConfig


class LiquidityRating(str, Enum):
    ILLIQUID = "ILLIQUID"
    ACCEPTABLE = "ACCEPTABLE"
    LIQUID = "LIQUID"


def compute_spread_pct(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    """None (unknown), never a fabricated number, if bid/ask aren't both
    available and positive."""
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2
    if mid <= 0:
        return None
    return (ask - bid) / mid


def passes_liquidity_filter(
    volume: Optional[int], open_interest: Optional[int], spread_pct: Optional[float], config: OptionSelectionConfig
) -> bool:
    """A missing value is treated as failing the filter, not as
    'acceptable by default' - unknown liquidity is not the same as good
    liquidity."""
    if volume is None or volume < config.min_volume:
        return False
    if open_interest is None or open_interest < config.min_open_interest:
        return False
    if spread_pct is None or spread_pct > config.max_spread_pct:
        return False
    return True


def rate_liquidity(
    volume: Optional[int], open_interest: Optional[int], spread_pct: Optional[float], config: OptionSelectionConfig
) -> LiquidityRating:
    if not passes_liquidity_filter(volume, open_interest, spread_pct, config):
        return LiquidityRating.ILLIQUID
    # "LIQUID" if comfortably clear of the minimum thresholds, not merely
    # scraping past them.
    assert volume is not None and open_interest is not None and spread_pct is not None
    if volume >= config.min_volume * 3 and open_interest >= config.min_open_interest * 3 and spread_pct <= config.max_spread_pct / 2:
        return LiquidityRating.LIQUID
    return LiquidityRating.ACCEPTABLE
