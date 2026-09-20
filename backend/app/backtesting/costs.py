"""
Transaction cost model: brokerage, taxes/fees, slippage, and spread.

DELIBERATE SIMPLIFICATION, READ BEFORE TRUSTING P&L NUMBERS: real Indian
intraday equity costs are a stack of small regulatory charges - STT,
exchange transaction charges, GST on brokerage, SEBI fees, stamp duty -
each individually small, each subject to change, and none of which I'm
willing to assert precise current rates for here. This model combines
them into two configurable percentages:
  - brokerage_pct: your broker's own charge
  - fees_pct: a stand-in for the STT/exchange/GST/SEBI/stamp-duty stack
Both are applied as CASH CHARGES on turnover (they don't move the fill
price). Slippage and spread are modeled separately because they DO move
the fill price - see apply_entry_slippage/apply_exit_slippage below.

Verify every default against your actual broker's cost sheet before
relying on backtest P&L - these are starting-point placeholders, not
regulatory facts.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    brokerage_pct: float = 0.0003   # 0.03% of turnover, per side
    fees_pct: float = 0.0005        # combined taxes/regulatory fees, per side (see docstring)
    slippage_pct: float = 0.0005    # adverse fill vs. theoretical trigger price, per side
    spread_pct: float = 0.0005      # half bid-ask spread cost, per side

    def validate(self) -> None:
        for name in ("brokerage_pct", "fees_pct", "slippage_pct", "spread_pct"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


def fill_price_long_entry(theoretical_price: float, costs: CostModel) -> float:
    """Buying gets a WORSE (higher) fill than the theoretical trigger price."""
    return theoretical_price * (1 + costs.slippage_pct + costs.spread_pct)


def fill_price_long_exit(theoretical_price: float, costs: CostModel) -> float:
    """Selling gets a WORSE (lower) fill than the theoretical exit price."""
    return theoretical_price * (1 - costs.slippage_pct - costs.spread_pct)


def fill_price_short_entry(theoretical_price: float, costs: CostModel) -> float:
    """Selling to open gets a WORSE (lower) fill than the theoretical trigger price."""
    return theoretical_price * (1 - costs.slippage_pct - costs.spread_pct)


def fill_price_short_exit(theoretical_price: float, costs: CostModel) -> float:
    """Buying to cover gets a WORSE (higher) fill than the theoretical exit price."""
    return theoretical_price * (1 + costs.slippage_pct + costs.spread_pct)


def cash_charges(entry_value: float, exit_value: float, costs: CostModel) -> float:
    """Brokerage + fees on both legs of the round trip, as a cash amount
    (not a price adjustment)."""
    rate = costs.brokerage_pct + costs.fees_pct
    return (entry_value + exit_value) * rate
