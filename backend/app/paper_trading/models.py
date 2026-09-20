"""
PaperPosition: one virtual (paper) position, tracked start to finish.

NO REAL ORDERS ARE EVER SENT FROM THIS MODULE. Everything here is
in-memory bookkeeping - see tests/test_paper_trading_no_real_orders.py,
which inspects this package's actual imports and fails the build if any
networking/broker library is ever imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.backtesting.costs import CostModel

Direction = Literal["LONG", "SHORT"]
ExitReason = Literal["TARGET_HIT", "STOP_LOSS_HIT", "MANUAL_CLOSE"]


@dataclass
class PaperPosition:
    id: str
    symbol: str
    direction: Direction
    entry_price: float
    quantity: int
    stop_loss: Optional[float]
    target: Optional[float]
    entry_time: Any

    # Context captured AT ENTRY - a historical snapshot, never
    # recalculated later (the whole point is to record what things looked
    # like at the moment the decision was made).
    opportunity_score_at_entry: Optional[float] = None
    market_condition: Optional[str] = None
    reason_for_entry: Optional[str] = None

    # Populated only once the position closes.
    exit_time: Optional[Any] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    r_multiple: Optional[float] = None

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    @property
    def is_win(self) -> Optional[bool]:
        """None while open - a win/loss classification requires a
        realized outcome, never guessed from an unresolved position."""
        if self.is_open or self.pnl is None:
            return None
        return self.pnl > 0


def close_position(
    position: PaperPosition,
    exit_time: Any,
    exit_price: float,
    exit_reason: ExitReason,
    cost_model: Optional["CostModel"] = None,
) -> PaperPosition:
    """
    Returns a NEW PaperPosition (does not mutate) with exit/P&L/R fields
    filled in. `entry_price`/`exit_price` always record the clean
    theoretical/trigger prices you'd actually see on screen - if
    `cost_model` is given (reusing Phase 12's CostModel), brokerage+fees
    are deducted from P&L as a cash cost on top, without distorting the
    recorded prices themselves. Slippage/spread price adjustment is
    deliberately NOT applied here (unlike Phase 12's backtest engine) -
    paper trading is meant to show clean, simple numbers by default.
    """
    if position.direction == "LONG":
        gross_pnl = (exit_price - position.entry_price) * position.quantity
        risk_per_share = (position.entry_price - position.stop_loss) if position.stop_loss is not None else None
    else:
        gross_pnl = (position.entry_price - exit_price) * position.quantity
        risk_per_share = (position.stop_loss - position.entry_price) if position.stop_loss is not None else None

    charges = 0.0
    if cost_model is not None:
        entry_value = position.entry_price * position.quantity
        exit_value = exit_price * position.quantity
        charges = (entry_value + exit_value) * (cost_model.brokerage_pct + cost_model.fees_pct)

    pnl = gross_pnl - charges

    entry_value = position.entry_price * position.quantity
    pnl_pct = (pnl / entry_value * 100) if entry_value > 0 else None

    r_multiple = None
    if risk_per_share is not None and risk_per_share > 0:
        pnl_per_share = pnl / position.quantity
        r_multiple = pnl_per_share / risk_per_share

    return PaperPosition(
        id=position.id, symbol=position.symbol, direction=position.direction,
        entry_price=position.entry_price, quantity=position.quantity,
        stop_loss=position.stop_loss, target=position.target, entry_time=position.entry_time,
        opportunity_score_at_entry=position.opportunity_score_at_entry,
        market_condition=position.market_condition, reason_for_entry=position.reason_for_entry,
        exit_time=exit_time, exit_price=exit_price, exit_reason=exit_reason,
        pnl=pnl, pnl_pct=pnl_pct, r_multiple=r_multiple,
    )
