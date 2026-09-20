import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402
from app.market_data.schemas import Candle  # noqa: E402
from app.market_data.validation import dedupe_candles, validate_and_clean  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"

TRADING_DAY = date(2026, 1, 27)  # ordinary Tuesday, not a holiday/weekend


@pytest.fixture()
def calendar():
    return NSECalendar.from_file(HOLIDAY_FILE)


def make_candle(hour, minute, close=100.0, timeframe=Timeframe.FIVE_MIN, d=TRADING_DAY):
    ts = datetime(d.year, d.month, d.day, hour, minute, tzinfo=IST)
    return Candle(
        symbol="TESTSYM", exchange="NSE", timeframe=timeframe, timestamp=ts,
        open=close, high=close, low=close, close=close, volume=1000,
    )


def test_candle_rejects_naive_timestamp():
    with pytest.raises(Exception):
        Candle(
            symbol="TESTSYM", exchange="NSE", timeframe=Timeframe.FIVE_MIN,
            timestamp=datetime(2026, 1, 27, 9, 15),  # naive - no tzinfo
            open=100, high=100, low=100, close=100, volume=1000,
        )


def test_candle_normalizes_other_timezone_to_ist():
    utc_ts = datetime(2026, 1, 27, 3, 45, tzinfo=ZoneInfo("UTC"))  # == 09:15 IST
    candle = Candle(
        symbol="TESTSYM", exchange="NSE", timeframe=Timeframe.FIVE_MIN,
        timestamp=utc_ts, open=100, high=100, low=100, close=100, volume=1000,
    )
    assert candle.timestamp.tzinfo == IST
    assert candle.timestamp.hour == 9 and candle.timestamp.minute == 15


def test_dedupe_keeps_last_occurrence():
    c1 = make_candle(9, 15, close=100.0)
    c2 = make_candle(9, 15, close=105.0)  # same timestamp, different value
    deduped, dups = dedupe_candles([c1, c2])
    assert len(deduped) == 1
    assert deduped[0].close == 105.0
    assert dups == [c1.timestamp]


def test_validate_and_clean_detects_gap(calendar):
    all_candles = [
        make_candle(9, 15), make_candle(9, 20), make_candle(9, 25),
        # 9:30 missing
        make_candle(9, 35),
    ]
    cleaned, report = validate_and_clean(all_candles, Timeframe.FIVE_MIN, calendar)
    assert len(cleaned) == 4
    assert datetime(2026, 1, 27, 9, 30, tzinfo=IST) in report.missing_timestamps


def test_validate_and_clean_drops_out_of_session_candle(calendar):
    late_candle = make_candle(18, 0)  # well after 15:30 close
    cleaned, report = validate_and_clean([make_candle(9, 15), late_candle], Timeframe.FIVE_MIN, calendar)
    assert len(cleaned) == 1
    assert late_candle.timestamp in report.out_of_session_dropped


def test_validate_and_clean_drops_out_of_session_on_holiday(calendar):
    holiday_candle = make_candle(9, 15, d=date(2026, 1, 26))  # Republic Day
    cleaned, report = validate_and_clean([holiday_candle], Timeframe.FIVE_MIN, calendar)
    assert cleaned == []
    assert holiday_candle.timestamp in report.out_of_session_dropped


def test_validate_and_clean_drops_misaligned_timestamp(calendar):
    misaligned = make_candle(9, 17)  # not on the 5-min grid (09:15, 09:20, ...)
    cleaned, report = validate_and_clean([make_candle(9, 15), misaligned], Timeframe.FIVE_MIN, calendar)
    assert len(cleaned) == 1
    assert misaligned.timestamp in report.misaligned_dropped


def test_validate_and_clean_does_not_fill_gaps_by_default(calendar):
    candles = [make_candle(9, 15), make_candle(9, 25)]  # 09:20 missing
    cleaned, report = validate_and_clean(candles, Timeframe.FIVE_MIN, calendar, fill_gaps=False)
    assert len(cleaned) == 2  # gap NOT fabricated
    assert report.gap_filled == []
    assert datetime(2026, 1, 27, 9, 20, tzinfo=IST) in report.missing_timestamps


def test_validate_and_clean_fills_gaps_when_opted_in(calendar):
    candles = [make_candle(9, 15, close=100.0), make_candle(9, 25, close=110.0)]  # 09:20 missing
    cleaned, report = validate_and_clean(candles, Timeframe.FIVE_MIN, calendar, fill_gaps=True)
    timestamps = [c.timestamp for c in cleaned]
    assert datetime(2026, 1, 27, 9, 20, tzinfo=IST) in timestamps
    assert datetime(2026, 1, 27, 9, 20, tzinfo=IST) in report.gap_filled
    filled = next(c for c in cleaned if c.timestamp.minute == 20)
    assert filled.close == 100.0  # forward-filled from the prior close
    assert filled.volume == 0


def test_validate_and_clean_deduplicates_before_gap_detection(calendar):
    c1 = make_candle(9, 15)
    c2 = make_candle(9, 15)  # duplicate
    cleaned, report = validate_and_clean([c1, c2], Timeframe.FIVE_MIN, calendar)
    assert len(cleaned) == 1
    assert report.duplicate_timestamps == [c1.timestamp]
