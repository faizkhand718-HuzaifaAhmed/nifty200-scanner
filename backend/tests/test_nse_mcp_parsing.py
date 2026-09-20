import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.exceptions import DataValidationError, ProviderAPIError  # noqa: E402
from app.market_data.providers.nse_mcp_parsing import (  # noqa: E402
    find_best_tool,
    parse_daily_candles,
    parse_quote,
    require_tool,
)


class FakeTool:
    def __init__(self, name, description=""):
        self.name = name
        self.description = description


def test_find_best_tool_matches_by_name():
    tools = [FakeTool("market_status"), FakeTool("equity_quote"), FakeTool("gainers_losers")]
    match = find_best_tool(tools, ["equity quote", "stock quote", "quote"])
    assert match is not None
    assert match.tool_name == "equity_quote"


def test_find_best_tool_prefers_more_specific_keyword_first():
    tools = [FakeTool("generic_quote_tool", "returns a generic quote"), FakeTool("equity_quote_tool", "individual stock quote")]
    match = find_best_tool(tools, ["individual stock", "quote"])
    assert match.tool_name == "equity_quote_tool"


def test_find_best_tool_matches_by_description_when_name_doesnt_match():
    tools = [FakeTool("tool_7", description="Returns the current equity quote for a symbol")]
    match = find_best_tool(tools, ["equity quote"])
    assert match.tool_name == "tool_7"


def test_find_best_tool_none_when_nothing_matches():
    tools = [FakeTool("unrelated_tool")]
    match = find_best_tool(tools, ["equity quote", "stock quote"])
    assert match is None


def test_require_tool_raises_with_helpful_message_listing_available_tools():
    tools = [FakeTool("foo"), FakeTool("bar")]
    with pytest.raises(ProviderAPIError, match="foo"):
        require_tool(tools, ["nonexistent keyword"], purpose="testing")


def test_require_tool_returns_name_on_match():
    tools = [FakeTool("nse_equity_quote")]
    name = require_tool(tools, ["equity quote", "quote"], purpose="testing")
    assert name == "nse_equity_quote"


def test_parse_quote_hand_computed_with_standard_field_names():
    now = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)
    fields = parse_quote({"ltp": 2905.5, "volume": 120000}, "RELIANCE", "NSE", now)
    assert fields["ltp"] == pytest.approx(2905.5)
    assert fields["volume"] == 120000
    assert fields["symbol"] == "RELIANCE"


def test_parse_quote_tries_alternate_field_name_variants():
    now = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)
    fields = parse_quote({"lastPrice": 100.0, "totalTradedVolume": 5000}, "TCS", "NSE", now)
    assert fields["ltp"] == pytest.approx(100.0)
    assert fields["volume"] == 5000


def test_parse_quote_missing_price_field_raises_clear_error():
    now = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(DataValidationError, match="RELIANCE"):
        parse_quote({"someOtherField": 1}, "RELIANCE", "NSE", now)


def test_parse_quote_defaults_volume_to_zero_when_absent():
    now = datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc)
    fields = parse_quote({"ltp": 100.0}, "X", "NSE", now)
    assert fields["volume"] == 0


def test_parse_daily_candles_hand_computed():
    rows = [
        {"date": "2026-01-27", "open": 100.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 50000},
        {"date": "2026-01-28", "open": 103.0, "high": 108.0, "low": 102.0, "close": 106.0, "volume": 60000},
    ]
    candles = parse_daily_candles(rows, "RELIANCE", "NSE", None)
    assert len(candles) == 2
    assert candles[0]["close"] == pytest.approx(103.0)
    assert candles[0]["timestamp"].date() == date(2026, 1, 27)
    assert candles[1]["volume"] == 60000


def test_parse_daily_candles_tries_alternate_field_names():
    rows = [{"Date": "2026-01-27", "Open": 100.0, "High": 105.0, "Low": 99.0, "Close": 103.0}]
    candles = parse_daily_candles(rows, "TCS", "NSE", None)
    assert candles[0]["close"] == pytest.approx(103.0)
    assert candles[0]["volume"] == 0


def test_parse_daily_candles_missing_required_field_raises_clear_error():
    rows = [{"date": "2026-01-27", "open": 100.0, "high": 105.0}]
    with pytest.raises(DataValidationError, match="low.*close|close.*low"):
        parse_daily_candles(rows, "RELIANCE", "NSE", None)


def test_parse_daily_candles_handles_alternate_date_formats():
    rows = [{"date": "27-01-2026", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    candles = parse_daily_candles(rows, "X", "NSE", None)
    assert candles[0]["timestamp"].date() == date(2026, 1, 27)
