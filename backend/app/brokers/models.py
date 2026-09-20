"""
Broker data models.

BrokerCredentials.from_env() is the ONLY populating path anywhere in this
codebase - no source file, config file, or default value ever contains a
real API key/secret/token. The dataclass's own field defaults are None,
never a placeholder string that could be mistaken for real config - see
tests/test_broker_credentials.py, which inspects the dataclass fields
directly to prove this.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Literal, Optional

Direction = Literal["LONG", "SHORT"]


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"


class OrderState(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class BrokerCredentials:
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, prefix: str) -> "BrokerCredentials":
        """Loads {PREFIX}_API_KEY, {PREFIX}_API_SECRET, {PREFIX}_ACCESS_TOKEN
        from the environment. A missing variable becomes None, never an
        empty-string placeholder that could silently pass an 'is it set'
        check."""
        return cls(
            api_key=os.environ.get(f"{prefix}_API_KEY"),
            api_secret=os.environ.get(f"{prefix}_API_SECRET"),
            access_token=os.environ.get(f"{prefix}_ACCESS_TOKEN"),
        )

    def is_complete(self) -> bool:
        return bool(self.api_key) and bool(self.api_secret)


@dataclass
class AuthResult:
    success: bool
    message: str = ""
    session_token: Optional[str] = None


@dataclass
class AccountInfo:
    account_id: str
    available_margin: float
    used_margin: float
    total_balance: float


@dataclass
class BrokerPosition:
    symbol: str
    direction: Direction
    quantity: int
    average_price: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None


@dataclass
class OrderRequest:
    symbol: str
    direction: Direction
    quantity: int
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None            # required for LIMIT/SL
    trigger_price: Optional[float] = None     # required for SL/SL-M
    product_type: str = "INTRADAY"


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    message: str = ""


@dataclass
class OrderStatusInfo:
    order_id: str
    state: OrderState
    filled_quantity: int = 0
    average_fill_price: Optional[float] = None
    updated_at: Optional[datetime] = None


@dataclass
class OrderModification:
    new_quantity: Optional[int] = None
    new_price: Optional[float] = None
    new_trigger_price: Optional[float] = None


@dataclass
class MarketDataSnapshot:
    symbol: str
    ltp: float
    timestamp: datetime
