"""
UnderlyingSignal: the separation point this phase requires. "The system
should first determine whether the underlying has a valid LONG/SHORT
setup, then determine the appropriate option contract."

This module contains ZERO logic for deciding direction or score - those
are Phase 6 (OpportunityScoringEngine) and Phase 7/10's job, already done
by the time an UnderlyingSignal exists. OptionsAnalysisEngine (engine.py)
only ever receives one as a finished input; it cannot compute one itself.
See tests/test_options_analysis_engine.py's
test_none_direction_never_selects_a_contract for the enforcement of this.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Direction = Literal["LONG", "SHORT", "NONE"]


@dataclass
class UnderlyingSignal:
    symbol: str
    direction: Direction
    opportunity_score: float
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None


def direction_to_option_type(direction: Direction) -> Optional[str]:
    """LONG -> CE, SHORT -> PE, NONE -> None. This is a definitional fact
    about what going long/short via options means, not a configurable
    'rule' with multiple reasonable interpretations - unlike strike/expiry
    preference, which genuinely are configurable (see config.py)."""
    if direction == "LONG":
        return "CE"
    if direction == "SHORT":
        return "PE"
    return None
