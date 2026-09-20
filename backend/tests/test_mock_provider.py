import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402
from app.market_data.exceptions import ProviderAPIError, SymbolNotFoundError  # noqa: E402
from app.market_data.providers.mock_provider import MockDataProvider  # noqa: E402
from app.market_data.schemas import MarketSessionState  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"

TRADING_DAY = date(2026, 1, 27)  # ordinary Tuesday


@pytest.fixture()
def calendar():
    return NSECalendar.from_file(HOLIDAY_FILE)


@pytest.fixture()
def provider(calendar):
    return MockDataProvider(calendar, seed=123)


# ---------------------------------------------------------------------------
# Historical candles
# ---------------------------------------------------------------------------

def test_historical_candles_only_on_trading_days(provider):
    # Range spans Republic Day (2026-01-26, holiday) and a weekend.
    candles = provider.get_historical_candles(
        "RELIANCE", "NSE", Timeframe.FIVE_MIN, date(2026, 1, 23), date(2026, 1, 27)
    )
    dates_present = {c.date_ist for c in candles}
    assert date(2026, 1, 26) not in dates_present  # holiday
    assert date(2026, 1, 24) not in dates_present  # Saturday
    assert date(2026, 1, 25) not in dates_present  # Sunday
    assert date(2026, 1, 23) in dates_present
    assert date(2026, 1, 27) in dates_present


def test_historical_candles_all_complete(provider):
    candles = provider.get_historical_candles(
        "RELIANCE", "NSE", Timeframe.FIFTEEN_MIN, date(2026, 1, 20), date(2026, 1, 27)
    )
    assert all(c.is_complete for c in candles)


def test_historical_candles_deterministic_across_calls(provider, calendar):
    c1 = provider.get_historical_candles("TCS", "NSE", Timeframe.FIVE_MIN, TRADING_DAY, TRADING_DAY)
    provider2 = MockDataProvider(calendar, seed=123)  # fresh instance, same seed
    c2 = provider2.get_historical_candles("TCS", "NSE", Timeframe.FIVE_MIN, TRADING_DAY, TRADING_DAY)
    assert [c.model_dump() for c in c1] == [c.model_dump() for c in c2]


def test_historical_close_independent_of_query_window(provider):
    """A given day's close must be the same whether you ask for a 1-day
    window or a 30-day window ending on that day - price(date) should not
    depend on which range happened to be queried."""
    wide = provider.get_historical_candles("INFY", "NSE", Timeframe.DAY, date(2026, 1, 1), TRADING_DAY)
    narrow = provider.get_historical_candles("INFY", "NSE", Timeframe.DAY, TRADING_DAY, TRADING_DAY)
    wide_close = next(c.close for c in wide if c.date_ist == TRADING_DAY)
    narrow_close = narrow[0].close
    assert wide_close == narrow_close


def test_historical_candles_empty_symbol_raises(provider):
    with pytest.raises(SymbolNotFoundError):
        provider.get_historical_candles("", "NSE", Timeframe.FIVE_MIN, TRADING_DAY, TRADING_DAY)


def test_historical_candles_no_trading_days_returns_empty(provider):
    # Sat -> Sun only
    candles = provider.get_historical_candles(
        "RELIANCE", "NSE", Timeframe.FIVE_MIN, date(2026, 1, 24), date(2026, 1, 25)
    )
    assert candles == []


# ---------------------------------------------------------------------------
# Intraday candles / incomplete-candle handling
# ---------------------------------------------------------------------------

def test_intraday_last_candle_marked_incomplete_mid_bar(provider):
    provider.set_clock(datetime(2026, 1, 27, 9, 27, tzinfo=IST))
    candles = provider.get_intraday_candles("RELIANCE", "NSE", Timeframe.FIVE_MIN)
    assert [c.timestamp.time() for c in candles] == [
        datetime(2026, 1, 27, 9, 15, tzinfo=IST).time(),
        datetime(2026, 1, 27, 9, 20, tzinfo=IST).time(),
        datetime(2026, 1, 27, 9, 25, tzinfo=IST).time(),
    ]
    assert candles[-1].is_complete is False
    assert all(c.is_complete for c in candles[:-1])


def test_intraday_candle_complete_once_bar_closes(provider):
    provider.set_clock(datetime(2026, 1, 27, 9, 30, tzinfo=IST))  # exactly at 09:25 bar's close
    candles = provider.get_intraday_candles("RELIANCE", "NSE", Timeframe.FIVE_MIN)
    assert candles[-1].timestamp.time() == datetime(2026, 1, 27, 9, 25, tzinfo=IST).time()
    assert candles[-1].is_complete is True


def test_intraday_empty_before_market_open(provider):
    provider.set_clock(datetime(2026, 1, 27, 8, 0, tzinfo=IST))
    candles = provider.get_intraday_candles("RELIANCE", "NSE", Timeframe.FIVE_MIN)
    assert candles == []


def test_intraday_empty_on_holiday(provider):
    provider.set_clock(datetime(2026, 1, 26, 11, 0, tzinfo=IST))  # Republic Day
    candles = provider.get_intraday_candles("RELIANCE", "NSE", Timeframe.FIVE_MIN)
    assert candles == []


# ---------------------------------------------------------------------------
# Latest price / volume
# ---------------------------------------------------------------------------

def test_latest_price_before_open_uses_previous_close(provider):
    provider.set_clock(datetime(2026, 1, 27, 8, 0, tzinfo=IST))
    quote = provider.get_latest_price("RELIANCE", "NSE")
    assert quote.volume == 0
    assert quote.ltp > 0


def test_latest_price_during_session_reflects_intraday_data(provider):
    provider.set_clock(datetime(2026, 1, 27, 10, 0, tzinfo=IST))
    quote = provider.get_latest_price("RELIANCE", "NSE")
    assert quote.volume > 0


def test_volume_zero_on_holiday(provider):
    provider.set_clock(datetime(2026, 1, 26, 11, 0, tzinfo=IST))
    assert provider.get_volume("RELIANCE", "NSE") == 0


# ---------------------------------------------------------------------------
# Market status / index quote
# ---------------------------------------------------------------------------

def test_market_status_matches_calendar(provider, calendar):
    provider.set_clock(datetime(2026, 1, 27, 12, 0, tzinfo=IST))
    status = provider.get_market_status()
    assert status.state == MarketSessionState.OPEN


def test_index_quote_has_change_and_pct(provider):
    provider.set_clock(datetime(2026, 1, 27, 12, 0, tzinfo=IST))
    quote = provider.get_index_quote("NIFTY 200")
    assert quote.index_name == "NIFTY 200"
    assert isinstance(quote.change_pct, float)


# ---------------------------------------------------------------------------
# Option chain (future capability)
# ---------------------------------------------------------------------------

def test_option_chain_returns_both_call_and_put_per_strike(provider):
    provider.set_clock(datetime(2026, 1, 27, 12, 0, tzinfo=IST))
    chain = provider.get_option_chain("RELIANCE")
    strikes = {c.strike for c in chain.contracts}
    for strike in strikes:
        types = {c.option_type for c in chain.contracts if c.strike == strike}
        assert len(types) == 2  # both CE and PE present


def test_option_chain_expiry_defaults_to_a_thursday(provider):
    provider.set_clock(datetime(2026, 1, 27, 12, 0, tzinfo=IST))  # a Tuesday
    chain = provider.get_option_chain("RELIANCE")
    assert chain.expiry.weekday() == 3  # Thursday


# ---------------------------------------------------------------------------
# Error simulation
# ---------------------------------------------------------------------------

def test_simulate_next_call_failure_raises_once_then_clears(provider):
    provider.simulate_next_call_failure(ProviderAPIError("simulated outage"))
    with pytest.raises(ProviderAPIError):
        provider.get_market_status()
    # second call should succeed normally
    status = provider.get_market_status()
    assert status is not None
