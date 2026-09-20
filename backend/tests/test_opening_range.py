import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.opening_range import opening_range_high_low  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")


def make_intraday(day: date, minute_offsets, highs, lows):
    base = datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST)
    timestamps = [base + timedelta(minutes=m) for m in minute_offsets]
    return (
        pd.Series(timestamps),
        pd.Series(highs, dtype=float),
        pd.Series(lows, dtype=float),
        pd.Series([day] * len(timestamps)),
    )


def test_opening_range_30_min_window():
    day = date(2026, 1, 27)
    # bars at 9:15, 9:20, ..., 9:45 (within window), then 9:50, 9:55 (after)
    timestamps, high, low, session_date = make_intraday(
        day,
        minute_offsets=[0, 5, 10, 15, 20, 25, 30, 35, 40],
        highs=[100, 105, 102, 108, 101, 103, 106, 120, 95],
        lows=[98, 99, 97, 100, 96, 98, 100, 90, 110],
    )
    result = opening_range_high_low(high, low, timestamps, session_date, window_minutes=30)

    # Window covers offsets 0..30 inclusive (9:15 to 9:45): highs
    # [100,105,102,108,101,103,106] -> running max reaches 108 at offset15
    # and stays 108 through offset30. lows similarly bottom out at 96.
    assert result["opening_range_high"].iloc[3] == pytest.approx(108.0)  # offset 15
    assert result["opening_range_high"].iloc[6] == pytest.approx(108.0)  # offset 30, window closes here
    # After the window (offsets 35, 40) - even though offset 35's actual
    # high (120) exceeds 108, the opening range must NOT change: it's a
    # fixed level once the window closes.
    assert result["opening_range_high"].iloc[7] == pytest.approx(108.0)
    assert result["opening_range_high"].iloc[8] == pytest.approx(108.0)

    assert result["opening_range_low"].iloc[6] == pytest.approx(96.0)
    assert result["opening_range_low"].iloc[8] == pytest.approx(96.0)  # held despite lower low(90) after window


def test_opening_range_resets_per_session():
    day1, day2 = date(2026, 1, 27), date(2026, 1, 28)
    ts1, h1, l1, sd1 = make_intraday(day1, [0, 5], [100, 110], [98, 95])
    ts2, h2, l2, sd2 = make_intraday(day2, [0, 5], [200, 205], [195, 190])

    timestamps = pd.concat([ts1, ts2], ignore_index=True)
    high = pd.concat([h1, h2], ignore_index=True)
    low = pd.concat([l1, l2], ignore_index=True)
    session_date = pd.concat([sd1, sd2], ignore_index=True)

    result = opening_range_high_low(high, low, timestamps, session_date, window_minutes=30)

    # Day 2's opening range must not be contaminated by day 1's values.
    assert result["opening_range_high"].iloc[2] == pytest.approx(200.0)
    assert result["opening_range_high"].iloc[3] == pytest.approx(205.0)
    assert result["opening_range_low"].iloc[3] == pytest.approx(190.0)


def test_opening_range_rejects_non_positive_window():
    timestamps, high, low, session_date = make_intraday(date(2026, 1, 27), [0], [100], [99])
    with pytest.raises(ValueError):
        opening_range_high_low(high, low, timestamps, session_date, window_minutes=0)
