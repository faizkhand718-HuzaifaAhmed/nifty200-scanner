"""
Data-transfer schemas for the market-data layer. Every provider (mock or
real) returns these types, never raw provider-SDK objects - this is the
contract the rest of the application (indicators, scoring, backtest,
frontend API) depends on, not any particular vendor's response shape.

All timestamps are timezone-aware and normalized to Asia/Kolkata. A naive
datetime anywhere in this layer is treated as a bug, not "assumed IST" -
callers must be explicit about timezone at the source.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_validator, model_validator

from app.market_data.enums import Timeframe

IST = ZoneInfo("Asia/Kolkata")


def _to_ist(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError(
            "timestamp must be timezone-aware - naive datetimes are rejected "
            "so we never silently guess a timezone. Localize to Asia/Kolkata "
            "(or the true source timezone) before constructing this object."
        )
    return v.astimezone(IST)


class Candle(BaseModel):
    symbol: str
    exchange: str = "NSE"
    timeframe: Timeframe
    timestamp: datetime  # candle OPEN time, tz-aware, normalized to IST
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    # False for the currently-forming candle (e.g. "today so far" on an
    # intraday pull). The indicator/scoring engine must exclude incomplete
    # candles by default - this is a primary look-ahead-bias guard.
    is_complete: bool = True

    @field_validator("timestamp")
    @classmethod
    def _tz_aware_ist(cls, v: datetime) -> datetime:
        return _to_ist(v)

    @model_validator(mode="after")
    def _sane_ohlc(self) -> "Candle":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open, close, and high")
        if self.volume < 0:
            raise ValueError("volume must not be negative")
        return self

    @property
    def date_ist(self) -> date:
        return self.timestamp.date()


class Quote(BaseModel):
    symbol: str
    exchange: str = "NSE"
    ltp: float
    volume: int = 0  # cumulative traded volume so far in the session
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _tz_aware_ist(cls, v: datetime) -> datetime:
        return _to_ist(v)


class MarketSessionState(str, Enum):
    PRE_OPEN = "PRE_OPEN"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    HOLIDAY = "HOLIDAY"


class MarketStatus(BaseModel):
    exchange: str = "NSE"
    state: MarketSessionState
    as_of: datetime
    reason: Optional[str] = None  # e.g. "Weekend", "Diwali-Balipratipada"
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None

    @field_validator("as_of", "next_open", "next_close")
    @classmethod
    def _tz_aware_ist(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        return _to_ist(v)


class IndexQuote(BaseModel):
    index_name: str  # e.g. "NIFTY 200", "NIFTY 50"
    value: float
    change: float
    change_pct: float
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _tz_aware_ist(cls, v: datetime) -> datetime:
        return _to_ist(v)


class OptionType(str, Enum):
    CALL = "CE"
    PUT = "PE"


class OptionContract(BaseModel):
    underlying: str
    expiry: date
    strike: float
    option_type: OptionType
    ltp: float
    open_interest: int
    implied_volatility: Optional[float] = None
    timestamp: datetime

    # Added in Phase 14 (options analysis) - optional/backward-compatible.
    # A real provider may not always populate all of these; Phase 14's
    # liquidity/selection logic treats a missing value as "unknown", never
    # as "acceptable" or "zero".
    volume: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    change_in_open_interest: Optional[int] = None

    @field_validator("timestamp")
    @classmethod
    def _tz_aware_ist(cls, v: datetime) -> datetime:
        return _to_ist(v)


class OptionChain(BaseModel):
    """Future capability. See MockDataProvider.get_option_chain docstring:
    mock contracts are a simplistic synthetic placeholder, not priced via
    a real option-pricing model - sufficient for wiring the interface and
    UI, not for analysis."""

    underlying: str
    expiry: date
    spot_price: float
    timestamp: datetime
    contracts: List[OptionContract]

    @field_validator("timestamp")
    @classmethod
    def _tz_aware_ist(cls, v: datetime) -> datetime:
        return _to_ist(v)
