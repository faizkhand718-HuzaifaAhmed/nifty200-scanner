"""
Position Size = Maximum Risk Amount / Stop Loss Distance.

This is the exact formula requested. It is DELIBERATELY reimplemented
here rather than imported from app.backtesting.position_sizing (which
has the same formula) - keeping risk_management fully self-contained,
with zero dependency on any other module in this codebase, is worth the
few lines of duplication. See
tests/test_risk_management_independence.py for the enforced boundary.
"""
from __future__ import annotations

from typing import Optional


def compute_position_size(max_risk_amount: float, entry_price: float, stop_loss: float) -> Optional[int]:
    """Returns None (never a fabricated size) if the stop distance is
    zero/negative or the resulting quantity rounds to zero."""
    if max_risk_amount <= 0:
        return None
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        return None
    quantity = int(max_risk_amount / stop_distance)
    return quantity if quantity > 0 else None


def compute_risk_reward(entry_price: float, stop_loss: float, target: Optional[float], direction: str) -> Optional[float]:
    if target is None:
        return None
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        return None
    reward = (target - entry_price) if direction == "LONG" else (entry_price - target)
    if reward <= 0:
        return None
    return reward / stop_distance
