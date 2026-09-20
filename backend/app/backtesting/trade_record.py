"""
TradeRecord: one trade's full lifecycle outcome, with realistic fill
prices (slippage + spread applied) and net P&L (brokerage + fees
deducted). This is where "winning trade" gets its real definition: NET
P&L > 0, not "which state it exited in" - a trade can hit its technical
target and still be a net loser after costs on a tight R:R, and this
model does not hide that.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from app.backtesting.costs import (
    CostModel,
    cash_charges,
    fill_price_long_entry,
    fill_price_long_exit,
    fill_price_short_entry,
    fill_price_short_exit,
)

Direction = Literal["LONG", "SHORT"]
ExitReason = Literal["TARGET_HIT", "STOP_LOSS_HIT", "STILL_OPEN"]


@dataclass
class TradeRecord:
    symbol: str
    direction: Direction
    entry_time: Any
    entry_price_theoretical: float
    entry_price_filled: float
    stop_price: float
    target_price: Optional[float]
    quantity: int
    exit_time: Optional[Any] = None
    exit_price_theoretical: Optional[float] = None
    exit_price_filled: Optional[float] = None
    exit_reason: ExitReason = "STILL_OPEN"
    gross_pnl: Optional[float] = None
    charges: Optional[float] = None
    net_pnl: Optional[float] = None
    r_multiple: Optional[float] = None

    @property
    def is_closed(self) -> bool:
        return self.exit_reason != "STILL_OPEN"

    @property
    def is_win(self) -> Optional[bool]:
        """None if still open - a win/loss classification requires a
        realized outcome, never guessed from an unresolved position."""
        if not self.is_closed or self.net_pnl is None:
            return None
        return self.net_pnl > 0


def build_trade_record(
    symbol: str,
    direction: Direction,
    entry_time: Any,
    entry_price_theoretical: float,
    stop_price: float,
    target_price: Optional[float],
    quantity: int,
    costs: CostModel,
) -> TradeRecord:
    """Called once, at the moment a position opens (ENTRY_TRIGGER). Fill
    price is computed immediately; P&L fields stay None until close_trade()."""
    entry_fill = (
        fill_price_long_entry(entry_price_theoretical, costs)
        if direction == "LONG"
        else fill_price_short_entry(entry_price_theoretical, costs)
    )
    return TradeRecord(
        symbol=symbol,
        direction=direction,
        entry_time=entry_time,
        entry_price_theoretical=entry_price_theoretical,
        entry_price_filled=entry_fill,
        stop_price=stop_price,
        target_price=target_price,
        quantity=quantity,
    )


def close_trade(
    trade: TradeRecord,
    exit_time: Any,
    exit_price_theoretical: float,
    exit_reason: Literal["TARGET_HIT", "STOP_LOSS_HIT"],
    costs: CostModel,
) -> TradeRecord:
    """Returns a NEW TradeRecord (does not mutate) with exit/P&L/R fields
    filled in - called once, at the bar the lifecycle reaches a terminal
    state."""
    if trade.direction == "LONG":
        exit_fill = fill_price_long_exit(exit_price_theoretical, costs)
        gross_pnl = (exit_fill - trade.entry_price_filled) * trade.quantity
        risk_per_share = trade.entry_price_theoretical - trade.stop_price
    else:
        exit_fill = fill_price_short_exit(exit_price_theoretical, costs)
        gross_pnl = (trade.entry_price_filled - exit_fill) * trade.quantity
        risk_per_share = trade.stop_price - trade.entry_price_theoretical

    entry_value = trade.entry_price_filled * trade.quantity
    exit_value = exit_fill * trade.quantity
    charges = cash_charges(entry_value, exit_value, costs)
    net_pnl = gross_pnl - charges

    r_multiple = None
    if risk_per_share > 0:
        net_pnl_per_share = net_pnl / trade.quantity
        r_multiple = net_pnl_per_share / risk_per_share

    return TradeRecord(
        symbol=trade.symbol,
        direction=trade.direction,
        entry_time=trade.entry_time,
        entry_price_theoretical=trade.entry_price_theoretical,
        entry_price_filled=trade.entry_price_filled,
        stop_price=trade.stop_price,
        target_price=trade.target_price,
        quantity=trade.quantity,
        exit_time=exit_time,
        exit_price_theoretical=exit_price_theoretical,
        exit_price_filled=exit_fill,
        exit_reason=exit_reason,
        gross_pnl=gross_pnl,
        charges=charges,
        net_pnl=net_pnl,
        r_multiple=r_multiple,
    )
