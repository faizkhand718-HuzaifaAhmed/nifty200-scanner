"""
Option Risk/Reward - ANOTHER EXPLICIT DESIGN DECISION, in the same spirit
as Phase 5's retest and Phase 10's stop/target methodology: there is no
real options-pricing model backing this system (Phase 3's option chain is
explicitly synthetic - see MockDataProvider.get_option_chain's own
docstring), so a genuine Greeks-based R:R (accounting for time decay,
implied volatility change, delta/gamma) is not something this system can
honestly compute.

What this DOES compute: the option's INTRINSIC VALUE ONLY (max(0,
underlying - strike) for a call, max(0, strike - underlying) for a put)
at the underlying's existing stop and target prices (from Phase 7/10 -
never recomputed here), then treats the change from current premium to
each of those intrinsic values as the risk/reward. This deliberately
IGNORES time value entirely - a real option's price at those underlying
levels would also reflect remaining time value and IV, which this ignores
completely. Treat this number as a rough directional estimate, not a
prediction of the option's actual future price. Review this before
relying on it for anything real.
"""
from __future__ import annotations

from typing import Optional


def estimate_intrinsic_value(underlying_price: float, strike: float, option_type: str) -> float:
    if option_type == "CE":
        return max(0.0, underlying_price - strike)
    return max(0.0, strike - underlying_price)


def compute_option_risk_reward(
    current_premium: float,
    strike: float,
    option_type: str,
    underlying_stop: Optional[float],
    underlying_target: Optional[float],
) -> Optional[float]:
    """None if the underlying has no stop/target, or if the resulting
    "risk" isn't positive (never a fabricated or divide-by-zero ratio)."""
    if underlying_stop is None or underlying_target is None:
        return None
    if current_premium <= 0:
        return None

    est_at_target = estimate_intrinsic_value(underlying_target, strike, option_type)
    est_at_stop = estimate_intrinsic_value(underlying_stop, strike, option_type)

    reward = est_at_target - current_premium
    risk = current_premium - est_at_stop
    if risk <= 0:
        return None
    return reward / risk
