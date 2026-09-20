"""
MockBrokerAdapter: a fully synthetic, in-memory implementation of
BrokerAdapter. No network calls anywhere in this file - useful for
testing the BrokerAdapter interface itself and any code that depends on
it, independent of any particular real broker's quirks or availability.
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


class MockBrokerAdapter(BrokerAdapter):
    def __init__(self, starting_balance: float = 100000.0):
        self._authenticated = False
        self._orders: Dict[str, OrderStatusInfo] = {}
        self._order_requests: Dict[str, OrderRequest] = {}
        self._positions: Dict[str, BrokerPosition] = {}
        self._next_order_id = 1
        self._account = AccountInfo(
            account_id="MOCK-0001", available_margin=starting_balance, used_margin=0.0, total_balance=starting_balance
        )

    @property
    def is_live(self) -> bool:
        return False

    def authenticate(self, credentials: BrokerCredentials) -> AuthResult:
        # A mock adapter accepts anything (including no credentials at
        # all) - it has nothing real to authenticate against. Real
        # adapters would actually validate `credentials` here.
        self._authenticated = True
        return AuthResult(success=True, message="mock authentication always succeeds", session_token="mock-session")

    def get_account_info(self) -> AccountInfo:
        return self._account

    def get_positions(self) -> List[BrokerPosition]:
        return list(self._positions.values())

    def place_order(self, order: OrderRequest) -> OrderResult:
        order_id = f"MOCK-ORD-{self._next_order_id}"
        self._next_order_id += 1

        fill_price = order.price if order.price is not None else 100.0  # a mock market fill price
        self._orders[order_id] = OrderStatusInfo(
            order_id=order_id, state=OrderState.COMPLETE, filled_quantity=order.quantity,
            average_fill_price=fill_price, updated_at=datetime.now(timezone.utc),
        )
        self._order_requests[order_id] = order

        existing = self._positions.get(order.symbol)
        if existing is None:
            self._positions[order.symbol] = BrokerPosition(
                symbol=order.symbol, direction=order.direction, quantity=order.quantity, average_price=fill_price,
            )
        else:
            existing.quantity += order.quantity

        return OrderResult(success=True, order_id=order_id, message="order filled (mock)")

    def get_order_status(self, order_id: str) -> OrderStatusInfo:
        status = self._orders.get(order_id)
        if status is None:
            raise OrderNotFoundError(f"no such order: {order_id}")
        return status

    def cancel_order(self, order_id: str) -> OrderResult:
        status = self._orders.get(order_id)
        if status is None:
            raise OrderNotFoundError(f"no such order: {order_id}")
        if status.state == OrderState.COMPLETE:
            return OrderResult(success=False, order_id=order_id, message="cannot cancel a completed order")
        status.state = OrderState.CANCELLED
        return OrderResult(success=True, order_id=order_id, message="order cancelled (mock)")

    def modify_order(self, order_id: str, modification: OrderModification) -> OrderResult:
        status = self._orders.get(order_id)
        if status is None:
            raise OrderNotFoundError(f"no such order: {order_id}")
        if status.state == OrderState.COMPLETE:
            return OrderResult(success=False, order_id=order_id, message="cannot modify a completed order")

        request = self._order_requests[order_id]
        if modification.new_quantity is not None:
            request.quantity = modification.new_quantity
        if modification.new_price is not None:
            request.price = modification.new_price
        if modification.new_trigger_price is not None:
            request.trigger_price = modification.new_trigger_price
        return OrderResult(success=True, order_id=order_id, message="order modified (mock)")

    def get_market_data(self, symbol: str) -> Optional[MarketDataSnapshot]:
        # A mock adapter has no real feed - returning None is honest
        # ("not supported by this adapter"), not a fabricated price.
        return None
