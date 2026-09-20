"""
NSEMCPProvider: implements this codebase's existing provider interfaces
(app/market_data/base.py) against NSE's official MCP servers -
https://www.nseindia.com/nse-mcp. No scraping, no unofficial libraries,
no third-party API keys - only the two documented, official endpoints.

HONESTY ABOUT WHAT THESE TWO SERVICES ACTUALLY SUPPORT (verified by
reading NSE's own page, not assumed): Bhavcopy is END-OF-DAY data only -
one OHLCV bar per trading day, 5 years of history. CM Market Live is a
LIVE SNAPSHOT/quote service (~1-3 minutes behind real-time) - it does not
document an intraday historical candle series. Neither service, as
documented, provides intraday (e.g. 5-minute/10-minute) HISTORICAL candle
bars. This provider therefore:
  - Supports get_historical_candles() for Timeframe.DAY only. Any other
    timeframe raises InvalidTimeframeError - this is not a bug, it's this
    provider being honest about a real data-source limitation rather than
    fabricating intraday bars that were never provided.
  - get_intraday_candles() raises ProviderAPIError with a clear
    explanation, for the same reason.
  - get_latest_price() and related snapshot methods work fully via CM
    Market Live.

This is a genuine, structural constraint of the two documented NSE MCP
services - not a limitation of this adapter. If true intraday candle
history becomes a requirement, that needs a provider actually built
against an intraday-capable source (e.g. a broker's historical-data API,
as scoped in the earlier options presented for this project).

VERIFICATION LIMIT, STATED PLAINLY: this file could not be executed
against the live NSE MCP servers from the sandbox this was built in (no
network access, and the `mcp` package is not installed there). It has
been syntax-checked and carefully reviewed, and every piece of parsing/
matching logic it depends on (nse_mcp_parsing.py) has been tested for
real against simulated data. The actual network connection needs to be
tested by you, post-deployment - see the project's status report for the
exact commands.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from app.market_data import mcp_client
from app.market_data.base import HistoricalOHLCVProvider, IntradayOHLCVProvider, LatestPriceProvider, VolumeProvider
from app.market_data.enums import Timeframe
from app.market_data.exceptions import InvalidTimeframeError, ProviderAPIError
from app.market_data.providers.nse_mcp_parsing import (
    KEYWORDS_EQUITY_QUOTE,
    KEYWORDS_HISTORICAL_OHLCV,
    parse_daily_candles,
    parse_quote,
    require_tool,
)
from app.market_data.schemas import Candle, Quote

IST = ZoneInfo("Asia/Kolkata")


class NSEMCPProvider(HistoricalOHLCVProvider, IntradayOHLCVProvider, LatestPriceProvider, VolumeProvider):
    def __init__(self, bhavcopy_url: str, cmmkt_url: str, auth_token: Optional[str] = None):
        self.bhavcopy_url = bhavcopy_url
        self.cmmkt_url = cmmkt_url
        self.auth_token = auth_token
        self._bhavcopy_tools = None
        self._cmmkt_tools = None

    def _get_bhavcopy_tools(self):
        if self._bhavcopy_tools is None:
            self._bhavcopy_tools = mcp_client.list_tools(self.bhavcopy_url, self.auth_token)
        return self._bhavcopy_tools

    def _get_cmmkt_tools(self):
        if self._cmmkt_tools is None:
            self._cmmkt_tools = mcp_client.list_tools(self.cmmkt_url, self.auth_token)
        return self._cmmkt_tools

    def get_latest_price(self, symbol: str, exchange: str) -> Quote:
        tool_name = require_tool(self._get_cmmkt_tools(), KEYWORDS_EQUITY_QUOTE, "individual stock quote")
        result = mcp_client.call_tool(self.cmmkt_url, tool_name, {"symbol": symbol})
        if result.data is None:
            raise ProviderAPIError(f"NSE MCP quote tool returned non-JSON data for {symbol}: {result.raw_text[:200]}")

        now = datetime.now(IST)
        fields = parse_quote(result.data, symbol, exchange, now)
        return Quote(**fields)

    def get_volume(self, symbol: str, exchange: str) -> int:
        return self.get_latest_price(symbol, exchange).volume

    def get_historical_candles(
        self, symbol: str, exchange: str, timeframe: Timeframe, start: date, end: date,
    ) -> List[Candle]:
        if timeframe != Timeframe.DAY:
            raise InvalidTimeframeError(
                f"NSE MCP's Bhavcopy service provides end-of-day data only (one bar per "
                f"trading day) - {timeframe.value} historical candles are not available "
                f"through this provider. See NSEMCPProvider's module docstring."
            )

        tool_name = require_tool(self._get_bhavcopy_tools(), KEYWORDS_HISTORICAL_OHLCV, "historical OHLCV")
        result = mcp_client.call_tool(
            self.bhavcopy_url, tool_name,
            {"symbol": symbol, "from_date": start.isoformat(), "to_date": end.isoformat()},
        )
        if result.data is None:
            raise ProviderAPIError(f"NSE MCP Bhavcopy tool returned non-JSON data for {symbol}: {result.raw_text[:200]}")

        rows = result.data if isinstance(result.data, list) else result.data.get("data", result.data.get("rows", []))
        if not isinstance(rows, list):
            raise ProviderAPIError(
                f"NSE MCP Bhavcopy response for {symbol} was not a list of rows and no "
                f"'data'/'rows' key was found - response shape may differ from what this "
                f"provider expects. Update get_historical_candles() once the real shape is known."
            )

        candle_dicts = parse_daily_candles(rows, symbol, exchange, IST)
        return [Candle(timeframe=Timeframe.DAY, **fields) for fields in candle_dicts]

    def get_daily_candles_for_lookback(self, symbol: str, exchange: str, lookback_days: int) -> List[Candle]:
        """Convenience wrapper: fetch enough calendar days back to cover
        `lookback_days` TRADING days (a rough 1.5x multiplier to account
        for weekends/holidays, generous rather than risking too few bars
        for e.g. a 200-day EMA)."""
        end = date.today()
        start = end - timedelta(days=int(lookback_days * 1.6) + 10)
        return self.get_historical_candles(symbol, exchange, Timeframe.DAY, start, end)

    def get_intraday_candles(
        self, symbol: str, exchange: str, timeframe: Timeframe, from_time: Optional[datetime] = None,
    ) -> List[Candle]:
        raise ProviderAPIError(
            "NSE MCP's CM Market Live service provides a current-price snapshot, not an "
            "intraday historical candle series - intraday candles are not available through "
            "this provider. See NSEMCPProvider's module docstring for what these two "
            "official NSE MCP services actually document."
        )
