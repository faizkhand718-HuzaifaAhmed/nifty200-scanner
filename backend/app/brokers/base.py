"""
BrokerAdapter: the abstraction every broker integration (mock, paper, or
a real future broker) implements identically. Nothing in this file knows
about any specific broker - "do not hard-code any specific broker" is
true of this module by construction, not by discipline.

`is_live` is the single source of truth for whether an adapter can send
REAL orders. MockBrokerAdapter and PaperBrokerAdapter both report False;
only a genuine live-broker adapter (none exists in this codebase yet)
would report True. safety.py's LiveTradingSafetyGate checks this
property directly - it does not infer "liveness" from a class name or
any other guessable signal.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from app.brokers.models import (
    AccountInfo,
    AuthResult,
    BrokerCredentials,
    BrokerPosition,
    MarketDataSnapshot,
    OrderModification,
    OrderRequest,
    OrderResult,
    OrderStatusInfo,
)


class BrokerAdapter(ABC):
    @property
    @abstractmethod
    def is_live(self) -> bool:
        """True only for an adapter that can place REAL orders with real
        money. Every non-live adapter (mock, paper) must return False."""

    @abstractmethod
    def authenticate(self, credentials: BrokerCredentials) -> AuthResult:
        """Never called with hardcoded credentials - `credentials` must
        come from BrokerCredentials.from_env() or an equivalent external
        source, never a literal in source code."""

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        ...

    @abstractmethod
    def get_positions(self) -> List[BrokerPosition]:
        ...

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult:
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatusInfo:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResult:
        ...

    @abstractmethod
    def modify_order(self, order_id: str, modification: OrderModification) -> OrderResult:
        ...

    @abstractmethod
    def get_market_data(self, symbol: str) -> Optional[MarketDataSnapshot]:
        """Market data 'where supported' - returns None if this adapter
        doesn't offer it (not every broker does, and this system's own
        Phase 3 MarketDataProvider may be the actual data source instead),
        never a fabricated quote."""
