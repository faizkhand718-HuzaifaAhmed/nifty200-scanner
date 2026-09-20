"""
Pure logic for the NSE MCP integration: which tool to call for a given
need, and how to parse whatever JSON comes back into this codebase's
Candle/Quote schemas.

WHY THIS IS SEPARATE FROM nse_mcp_provider.py: this file has no I/O and no
dependency on the `mcp` package - every function here takes already-
available data (a list of discovered tool names, or an already-fetched
JSON blob) and returns a plain result. That's what makes it possible to
test this logic for real in a sandbox with no network access and no `mcp`
package installed (see tests/test_nse_mcp_parsing.py) - only the actual
network call in nse_mcp_provider.py/mcp_client.py is untestable here.

IMPORTANT, STATED PLAINLY: the exact tool names NSE's MCP servers expose
could not be verified from this sandbox (no network access to call
list_tools() against the live server). The keyword-matching approach
below is a deliberate response to that uncertainty - rather than
hardcoding a guessed tool name and silently calling the wrong thing (or
nothing) if it's wrong, this searches discovered tool names/descriptions
for the best match and fails LOUDLY, listing what it actually found, if
nothing matches well enough. Once you run this against the real server,
check the "matched tool" field in the raised error or logs - if it picked
the wrong tool, tighten KEYWORDS_* below with the exact real name.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

from app.market_data.exceptions import DataValidationError, ProviderAPIError

KEYWORDS_EQUITY_QUOTE = ["equity quote", "stock quote", "individual stock", "quote"]
KEYWORDS_HISTORICAL_OHLCV = ["price history", "ohlcv", "historical", "bhavcopy"]
KEYWORDS_INDEX_QUOTE = ["index", "nifty"]
KEYWORDS_GAINERS = ["gainers", "top gainers"]
KEYWORDS_LOSERS = ["losers", "top losers"]
KEYWORDS_MARKET_STATUS = ["freshness", "market status", "data freshness"]
KEYWORDS_52_WEEK = ["52-week", "52 week", "high & low", "high and low"]


@dataclass
class ToolMatch:
    tool_name: str
    matched_on_keyword: str


def find_best_tool(available_tools: Sequence[Any], keywords: List[str]) -> Optional[ToolMatch]:
    """`available_tools` is whatever list_tools() returned - objects (or
    dicts) with `.name` / `.description` (or ["name"]/["description"]).
    Returns the first tool whose name or description contains any
    keyword, checking keywords in priority order (index 0 = most
    specific) before falling back to a later, broader keyword. None if
    nothing matches any keyword at all."""
    def _name(t):
        return (getattr(t, "name", None) or t.get("name", "")) if not isinstance(t, str) else t

    def _description(t):
        if isinstance(t, str):
            return ""
        return getattr(t, "description", None) or (t.get("description", "") if isinstance(t, dict) else "")

    for keyword in keywords:
        for tool in available_tools:
            haystack = f"{_name(tool)} {_description(tool)}".lower()
            if keyword.lower() in haystack:
                return ToolMatch(tool_name=_name(tool), matched_on_keyword=keyword)
    return None


def require_tool(available_tools: Sequence[Any], keywords: List[str], purpose: str) -> str:
    match = find_best_tool(available_tools, keywords)
    if match is None:
        available_names = [
            (getattr(t, "name", None) or (t.get("name", "?") if isinstance(t, dict) else str(t)))
            for t in available_tools
        ]
        raise ProviderAPIError(
            f"no NSE MCP tool found for {purpose!r} (searched for keywords {keywords}). "
            f"Tools actually available on this server: {available_names}. "
            f"Update the KEYWORDS_* list in app/market_data/providers/nse_mcp_parsing.py "
            f"once you know the real tool name."
        )
    return match.tool_name


def _first_present(data: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def parse_quote(data: Dict[str, Any], symbol: str, exchange: str, now: datetime) -> Dict[str, Any]:
    """Returns a plain dict with the fields needed to build a Quote -
    the caller (nse_mcp_provider.py) constructs the actual pydantic
    Quote so this function stays free of that dependency for testing."""
    ltp = _first_present(data, ["ltp", "lastPrice", "last_price", "LTP", "lastTradedPrice"])
    volume = _first_present(data, ["volume", "totalTradedVolume", "totalTradedVolumeQty"])

    if ltp is None:
        raise DataValidationError(
            f"NSE MCP quote response for {symbol} had no recognizable price field. "
            f"Raw keys present: {sorted(data.keys())}. Update parse_quote()'s field list "
            f"once you know the real field name."
        )

    return {
        "symbol": symbol, "exchange": exchange, "ltp": float(ltp),
        "volume": int(volume) if volume is not None else 0, "timestamp": now,
    }


def parse_daily_candles(rows: List[Dict[str, Any]], symbol: str, exchange: str, ist_tz) -> List[Dict[str, Any]]:
    """Returns a list of plain dicts (one per candle) - the caller builds
    actual Candle objects. Each row is expected to represent one trading
    day's OHLCV from Bhavcopy; field names tried in common variants."""
    out = []
    for row in rows:
        date_val = _first_present(row, ["date", "Date", "tradeDate", "TIMESTAMP"])
        open_val = _first_present(row, ["open", "Open", "OPEN_PRICE", "OpenPrice"])
        high_val = _first_present(row, ["high", "High", "HIGH_PRICE", "HighPrice"])
        low_val = _first_present(row, ["low", "Low", "LOW_PRICE", "LowPrice"])
        close_val = _first_present(row, ["close", "Close", "CLOSE_PRICE", "ClosePrice"])
        volume_val = _first_present(row, ["volume", "Volume", "TTL_TRD_QNTY", "TotalTradedQuantity"])

        missing = [
            name for name, val in [
                ("date", date_val), ("open", open_val), ("high", high_val),
                ("low", low_val), ("close", close_val),
            ] if val is None
        ]
        if missing:
            raise DataValidationError(
                f"NSE MCP historical row for {symbol} is missing field(s) {missing}. "
                f"Raw keys present: {sorted(row.keys())}. Update parse_daily_candles()'s "
                f"field list once you know the real field names."
            )

        parsed_date = date_val if isinstance(date_val, date) and not isinstance(date_val, datetime) else _parse_date_string(str(date_val))
        timestamp = datetime(parsed_date.year, parsed_date.month, parsed_date.day, 9, 15, tzinfo=ist_tz)

        out.append({
            "symbol": symbol, "exchange": exchange, "timestamp": timestamp,
            "open": float(open_val), "high": float(high_val), "low": float(low_val), "close": float(close_val),
            "volume": int(volume_val) if volume_val is not None else 0, "is_complete": True,
        })
    return out


def _parse_date_string(raw: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise DataValidationError(f"could not parse date {raw!r} from NSE MCP response in any known format")
