"""
Configurable thresholds for the ranking engine. None of these are
backtested "correct" values - they're a first draft to be tuned once
backtesting can measure their actual effect on outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RankingConfig:
    # A symbol's leading (higher of LONG/SHORT) Opportunity Score must
    # clear this to be reported as a valid DIRECTION at all. Below this,
    # direction is "NONE" - the score is still shown, just not flagged as
    # a valid setup.
    min_valid_score: float = 40.0

    # Entry Status thresholds (see engine.py docstring for the full rule).
    watch_score_threshold: float = 50.0
    ready_score_threshold: float = 70.0

    # Risk/Reward fallback: when no usable pivot level exists for the
    # stop/target, use this many ATRs instead (see risk_reward.py).
    stop_atr_multiple: float = 1.5
    target_atr_multiple: float = 3.0
