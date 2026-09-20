"""
Risk/Reward calculation - ANOTHER EXPLICIT DESIGN DECISION, in the same
spirit as Phase 5's retest definition: there is no single universally
"correct" way to set a stop-loss and target, so this is a documented
choice, not an objective truth.

As implemented: the previous day's classic pivot ladder (already computed
in Phase 4 - support/S1-S3, resistance/R1-R3) is used as the primary
stop/target reference, since it's grounded in an already-explainable
level rather than an arbitrary multiple. It falls back to an ATR multiple
only when no usable pivot level exists (e.g. the first trading day with no
prior-day levels yet, or price has already moved beyond the outer band).

Review this against your actual risk-management rules before relying on
it - the "right" stop/target methodology genuinely depends on your
trading style.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple


def _valid(x: Optional[float]) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def long_risk_reward(
    close: float,
    atr: float,
    support: Optional[float],
    r1: Optional[float],
    r2: Optional[float],
    r3: Optional[float],
    stop_atr_multiple: float,
    target_atr_multiple: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Returns (stop_loss, target, risk_reward_ratio). The ratio is None
    if risk or reward can't be made positive (e.g. price already sits at
    or below the chosen stop level) - never a fabricated/divide-by-zero
    number."""
    if not _valid(close) or not _valid(atr):
        return None, None, None

    stop = support if (_valid(support) and support < close) else close - stop_atr_multiple * atr

    target = None
    for level in (r1, r2, r3):
        if _valid(level) and level > close:
            target = level
            break
    if target is None:
        target = close + target_atr_multiple * atr

    risk = close - stop
    reward = target - close
    if risk <= 0 or reward <= 0:
        return stop, target, None
    return stop, target, reward / risk


def short_risk_reward(
    close: float,
    atr: float,
    resistance: Optional[float],
    s1: Optional[float],
    s2: Optional[float],
    s3: Optional[float],
    stop_atr_multiple: float,
    target_atr_multiple: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Mirror of long_risk_reward: stop above (resistance/R1 fallback ATR),
    target below (support ladder S1-S3, fallback ATR)."""
    if not _valid(close) or not _valid(atr):
        return None, None, None

    stop = resistance if (_valid(resistance) and resistance > close) else close + stop_atr_multiple * atr

    target = None
    for level in (s1, s2, s3):
        if _valid(level) and level < close:
            target = level
            break
    if target is None:
        target = close - target_atr_multiple * atr

    risk = stop - close
    reward = close - target
    if risk <= 0 or reward <= 0:
        return stop, target, None
    return stop, target, reward / risk
