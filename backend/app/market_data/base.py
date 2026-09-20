"""
Abstract interfaces for the market-data layer.

Each capability is its own small ABC (interface segregation) so application
code can depend on only what it actually needs - e.g. the backtest engine
depends on HistoricalOHLCVProvider, the live dashboard depends on
LatestPriceProvider + MarketStatusProvider - without pulling in a dependency
on a fully-featured broker client.

`MarketDataProvider` composes all of them: a concrete provider (mock or
real) implements every capability, but callers should type-hint against the
narrowest interface that satisfies their need, not this composed type.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional

from app.market_data.enums import Timeframe
from app.market_data.schemas import Candle, IndexQuote, MarketStatus, OptionChain, Quote


class HistoricalOHLCVProvider(ABC):
    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: date,
        end: date,
    ) -> List[Candle]:
        """Closed, historical candles between start and end (inclusive),
        for dates that were trading days. All returned candles must have
        is_complete=True - historical data should never contain a
        currently-forming bar."""


class IntradayOHLCVProvider(ABC):
    @abstractmethod
    def get_intraday_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        from_time: Optional[datetime] = None,
    ) -> List[Candle]:
        """Today's candles for `timeframe`, from session open (or
        `from_time` if given) up to now. If the current time falls inside
        an in-progress candle, that last candle must be returned with
        is_complete=False - callers doing indicator/scoring math must
        exclude it to avoid acting on a partial bar."""


class LatestPriceProvider(ABC):
    @abstractmethod
    def get_latest_price(self, symbol: str, exchange: str) -> Quote:
        """Last traded price. Outside market hours this is the last
        available price (e.g. previous close), not a fabricated tick."""


class VolumeProvider(ABC):
    @abstractmethod
    def get_volume(self, symbol: str, exchange: str) -> int:
        """Cumulative traded volume so far in the current session (0
        before market open)."""


class MarketStatusProvider(ABC):
    @abstractmethod
    def get_market_status(self, exchange: str = "NSE") -> MarketStatus:
        """Whether the market is currently open, and why not if closed
        (weekend, holiday, before/after session hours)."""


class IndexDataProvider(ABC):
    @abstractmethod
    def get_index_quote(self, index_name: str) -> IndexQuote:
        """Current value of a market index (e.g. NIFTY 50, NIFTY 200)."""


class OptionChainProvider(ABC):
    @abstractmethod
    def get_option_chain(self, underlying: str, expiry: Optional[date] = None) -> OptionChain:
        """Future capability. Concrete real-provider adapters may raise
        NotImplementedError until option-chain support is actually wired
        up; the interface exists now so downstream code can be written
        against it without a future breaking change."""


class MarketDataProvider(
    HistoricalOHLCVProvider,
    IntradayOHLCVProvider,
    LatestPriceProvider,
    VolumeProvider,
    MarketStatusProvider,
    IndexDataProvider,
    OptionChainProvider,
    ABC,
):
    """Composed interface: a concrete provider (MockDataProvider, and later
    a real broker/vendor adapter) implements every capability above. Prefer
    depending on the individual capability interfaces in application code."""
