"""
PaperBrokerAdapter: exposes Phase 13's PaperTradingEngine through the SAME
BrokerAdapter interface a real broker would use. This is what makes
"paper trading remains the default mode" concrete rather than aspirational
- code written against BrokerAdapter works identically whether the
factory hands it this adapter or a real one later.

place_order() requires `order.price` to be set. This adapter has no live
market-data source wired in (deliberately decoupled from app.market_data,
same reasoning as every other module boundary in this codebase) - it
cannot fabricate a fill price for a MARKET order with no price attached.
Pass the current price explicitly via order.price.

Paper "orders" fill instantly (there's no real exchange matching to wait
on) - the resulting PaperPosition is the actual unit of ongoing state,
tracked exactly as Phase 13 already does. Cancel/modify are therefore not
meaningful for an already-filled paper order and return success=False
with a clear message rather than pretending to support them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.brokers.base import BrokerAdapter
from app.brokers.exceptions import OrderNotFoundError
from app.brokers.models import (
    AccountInfo,
    AuthResult,
    BrokerCredentials,
    BrokerPosition,
    MarketDataSnapshot,
    OrderModification,
    OrderRequest,
    OrderResult,
    OrderState,
    OrderStatusInfo,
)
from app.paper_trading.engine import PaperTradingEngine


class PaperBrokerAdapter(BrokerAdapter):
    def __init__(self, engine: Optional[PaperTradingEngine] = None, account_capital: float = 100000.0):
        self._engine = engine or PaperTradingEngine()
        self._account_capital = account_capital
        self._order_to_position: Dict[str, str] = {}
        self._next_order_id = 1

    @property
    def is_live(self) -> bool:
        return False

    def authenticate(self, credentials: BrokerCredentials) -> AuthResult:
        return AuthResult(success=True, message="paper trading requires no real authentication")

    def get_account_info(self) -> AccountInfo:
        closed = self._engine.get_closed_positions()
        realized_pnl = sum(p.pnl for p in closed if p.pnl is not None)
        balance = self._account_capital + realized_pnl
        return AccountInfo(account_id="PAPER-0001", available_margin=balance, used_margin=0.0, total_balance=balance)

    def get_positions(self) -> List[BrokerPosition]:
        return [
            BrokerPosition(symbol=p.symbol, direction=p.direction, quantity=p.quantity, average_price=p.entry_price)
            for p in self._engine.get_open_positions()
        ]

    def place_order(self, order: OrderRequest) -> OrderResult:
        if order.price is None:
            return OrderResult(
                success=False,
                message="PaperBrokerAdapter requires order.price - no live market-data source is wired into this adapter",
            )
        position = self._engine.open_position(
            symbol=order.symbol,
            direction=order.direction,
            entry_price=order.price,
            quantity=order.quantity,
            stop_loss=order.trigger_price,
            target=None,
            entry_time=datetime.now(timezone.utc),
        )
        order_id = f"PAPER-ORD-{self._next_order_id}"
        self._next_order_id += 1
        self._order_to_position[order_id] = position.id
        return OrderResult(success=True, order_id=order_id, message="paper position opened")

    def get_order_status(self, order_id: str) -> OrderStatusInfo:
        position_id = self._order_to_position.get(order_id)
        position = self._engine.get_position(position_id) if position_id else None
        if position is None:
            raise OrderNotFoundError(f"no such order: {order_id}")
        return OrderStatusInfo(
            order_id=order_id, state=OrderState.COMPLETE, filled_quantity=position.quantity,
            average_fill_price=position.entry_price,
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        return OrderResult(
            success=False, order_id=order_id,
            message="paper orders fill instantly and cannot be cancelled - close the resulting position instead",
        )

    def modify_order(self, order_id: str, modification: OrderModification) -> OrderResult:
        return OrderResult(
            success=False, order_id=order_id,
            message="paper orders fill instantly and cannot be modified",
        )

    def get_market_data(self, symbol: str) -> Optional[MarketDataSnapshot]:
        return None
