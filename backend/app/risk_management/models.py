"""
Data models for the risk management boundary.

ProposedTrade is the ONLY thing risk_management accepts as input - a
plain data structure with no knowledge of which engine produced it. This
is what makes "risk management must operate independently from the
signal engine" true structurally: whether a trade came from Phase 5's
setup detection, Phase 10's entry engine, Phase 15's ML layer, or a human
clicking a button, it looks identical by the time it reaches here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional

Direction = Literal["LONG", "SHORT"]


@dataclass
class ProposedTrade:
    symbol: str
    direction: Direction
    entry_price: float
    stop_loss: float
    target: Optional[float] = None
    market_data_timestamp: Optional[datetime] = None


@dataclass
class RiskDecision:
    approved: bool
    position_size: Optional[int] = None
    position_value: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_reward: Optional[float] = None
    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
