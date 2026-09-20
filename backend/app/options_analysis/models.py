"""
OptionAnalysisResult: the full output, covering all 13 requested fields
plus the underlying context (1-2) that determined whether any option
selection happened at all (3-13).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.options_analysis.liquidity import LiquidityRating
from app.options_analysis.underlying_signal import Direction


@dataclass
class OptionAnalysisResult:
    # 1-2: underlying signal - decided entirely upstream (Phases 6/7/10),
    # never by this module.
    underlying_symbol: str
    underlying_direction: Direction
    underlying_opportunity_score: float

    # 3-13: option contract fields - all None if underlying_direction is
    # "NONE", or if no contract met the liquidity gate. Never fabricated.
    option_type: Optional[str] = None          # "CE" / "PE"
    expiry: Optional[date] = None
    strike: Optional[float] = None
    premium: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    change_in_open_interest: Optional[int] = None
    implied_volatility: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread_pct: Optional[float] = None
    liquidity: Optional[LiquidityRating] = None
    risk_reward: Optional[float] = None

    # Provenance - why this contract (or no contract) was chosen. Always
    # populated, so "no option selected" is explained, not silent.
    selection_note: str = ""

    @property
    def has_contract(self) -> bool:
        return self.strike is not None
