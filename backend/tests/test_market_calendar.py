import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402
from app.market_data.schemas import MarketSessionState  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"


@pytest.fixture()
def calendar():
    return NSECalendar.from_file(HOLIDAY_FILE)


def test_loads_holidays_from_file(calendar):
    assert calendar.is_holiday(date(2026, 1, 26))  # Republic Day
    assert calendar.holiday_name(date(2026, 1, 26)) == "Republic Day"
    assert not calendar.is_holiday(date(2026, 1, 27))


def test_weekend_is_not_a_trading_day(calendar):
    saturday = date(2026, 1, 24)
    assert saturday.weekday() == 5
    assert not calendar.is_trading_day(saturday)


def test_holiday_is_not_a_trading_day(calendar):
    assert not calendar.is_trading_day(date(2026, 1, 26))


def test_ordinary_weekday_is_a_trading_day(calendar):
    assert calendar.is_trading_day(date(2026, 1, 27))  # day after Republic Day, a Tuesday


def test_next_trading_day_skips_weekend_and_holiday(calendar):
    # Friday 2026-01-23 -> Sat/Sun weekend -> Mon 2026-01-26 is Republic Day
    # -> next trading day should be Tue 2026-01-27
    assert calendar.next_trading_day(date(2026, 1, 23)) == date(2026, 1, 27)


def test_session_timestamps_five_min_count(calendar):
    d = date(2026, 1, 27)
    timestamps = calendar.session_timestamps(d, Timeframe.FIVE_MIN)
    assert timestamps[0] == datetime(2026, 1, 27, 9, 15, tzinfo=IST)
    assert timestamps[-1] <= datetime(2026, 1, 27, 15, 30, tzinfo=IST)
    assert all(ts.tzinfo is not None for ts in timestamps)


def test_session_timestamps_empty_on_non_trading_day(calendar):
    assert calendar.session_timestamps(date(2026, 1, 26), Timeframe.FIVE_MIN) == []


def test_session_timestamps_daily_is_single_open_timestamp(calendar):
    d = date(2026, 1, 27)
    timestamps = calendar.session_timestamps(d, Timeframe.DAY)
    assert timestamps == [datetime(2026, 1, 27, 9, 15, tzinfo=IST)]


def test_market_status_holiday(calendar):
    as_of = datetime(2026, 1, 26, 11, 0, tzinfo=IST)
    status = calendar.get_market_status(as_of)
    assert status.state == MarketSessionState.HOLIDAY
    assert status.reason == "Republic Day"


def test_market_status_weekend(calendar):
    as_of = datetime(2026, 1, 24, 11, 0, tzinfo=IST)
    status = calendar.get_market_status(as_of)
    assert status.state == MarketSessionState.HOLIDAY
    assert status.reason == "Weekend"


def test_market_status_pre_open(calendar):
    as_of = datetime(2026, 1, 27, 8, 0, tzinfo=IST)
    status = calendar.get_market_status(as_of)
    assert status.state == MarketSessionState.PRE_OPEN
    assert status.next_open == datetime(2026, 1, 27, 9, 15, tzinfo=IST)


def test_market_status_open(calendar):
    as_of = datetime(2026, 1, 27, 12, 0, tzinfo=IST)
    status = calendar.get_market_status(as_of)
    assert status.state == MarketSessionState.OPEN
    assert status.next_close == datetime(2026, 1, 27, 15, 30, tzinfo=IST)


def test_market_status_closed_after_hours(calendar):
    as_of = datetime(2026, 1, 27, 18, 0, tzinfo=IST)
    status = calendar.get_market_status(as_of)
    assert status.state == MarketSessionState.CLOSED
