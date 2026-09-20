"""
Position sizing: fixed-fractional risk. Risking a configured percentage
of capital per trade is the standard convention for this kind of report -
it's what makes "Average R" and "Expectancy" meaningful figures rather
than artifacts of an arbitrary fixed share count.
"""
from __future__ import annotations

from typing import Optional


def compute_quantity(
    capital: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_price: float,
) -> Optional[int]:
    """
    Returns the number of shares to trade such that a full stop-out loses
    approximately `risk_per_trade_pct` of `capital` (before costs - costs
    are additional, not netted into the sizing itself, so realized risk is
    slightly more than the nominal target, same as in real trading).
    Returns None if the risk-per-share is zero or negative (can't size a
    position with no defined risk), or if capital/risk_per_trade_pct are
    non-positive.
    """
    if capital <= 0 or risk_per_trade_pct <= 0:
        return None
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0:
        return None

    risk_amount = capital * risk_per_trade_pct
    quantity = int(risk_amount / risk_per_share)
    return quantity if quantity > 0 else None
