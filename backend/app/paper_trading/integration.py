"""
Bridges Phase 10's TradeLifecycle to the paper-trading engine: "when an
ENTRY signal occurs, allow the user to create a virtual position." The
ENTRY signal is Phase 10's ENTRY_TRIGGER state; "allow the user" means
this function is called on explicit user action (a UI button), never
automatically on every trigger - PaperTradingEngine.open_position() has
no idea this helper exists and would happily be called directly too.
"""
from __future__ import annotations

from typing import Any, Optional

from app.entry_engine.state_machine import TradeLifecycle
from app.entry_engine.states import TradeState
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.models import PaperPosition


def paper_trade_from_lifecycle(
    engine: PaperTradingEngine,
    lifecycle: TradeLifecycle,
    symbol: str,
    entry_time: Any,
    quantity: int,
    opportunity_score_at_entry: Optional[float] = None,
    market_condition: Optional[str] = None,
    reason_for_entry: Optional[str] = None,
) -> PaperPosition:
    if lifecycle.state != TradeState.ENTRY_TRIGGER:
        raise ValueError(
            f"lifecycle must be in ENTRY_TRIGGER state to open a paper trade from it, "
            f"got {lifecycle.state.value}"
        )
    if lifecycle.entry_price is None:
        raise ValueError("lifecycle has no entry_price set - cannot open a position without one")

    reason = reason_for_entry or (
        f"{lifecycle.config.entry_method.value} entry trigger ({lifecycle.direction})"
    )

    return engine.open_position(
        symbol=symbol,
        direction=lifecycle.direction,
        entry_price=lifecycle.entry_price,
        quantity=quantity,
        stop_loss=lifecycle.stop,
        target=lifecycle.target,
        entry_time=entry_time,
        opportunity_score_at_entry=opportunity_score_at_entry,
        market_condition=market_condition,
        reason_for_entry=reason,
    )
